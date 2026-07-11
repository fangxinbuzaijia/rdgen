import io
from pathlib import Path
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import os
import secrets
import re
import requests
import base64
import json
import uuid
import pyzipper
import hmac
import hashlib
import time
import mimetypes
import copy
from django.conf import settings as _settings
from django.db.models import Q
from .forms import GenerateForm
from .models import GithubRun
from PIL import Image
from django.http import FileResponse, Http404

BOOLEAN_SETTING_FIELDS = {
    'hideSecuritySettings': 'hide-security-settings',
    'hideNetworkSettings': 'hide-network-settings',
    'hideServerSettings': 'hide-server-settings',
    'hideRemotePrinterSettings': 'hide-remote-printer-settings',
    'hide_account': 'hide-account',
    'remove_preset_password_warning': 'remove-preset-password-warning',
    'hideProxySettings': 'hide-proxy-settings',
    'hideWebsocketSettings': 'hide-websocket-settings',
    'collapse_toolbar': 'collapse-toolbar',
    'privacy_mode': 'privacy-mode',
    'privacy_wallpaper': 'privacy-wallpaper',
    'hide_username_on_card': 'hide-username-on-card',
    'viewOnly': 'view-only',
    'hide_sensitive_ui': 'hide-sensitive-ui',
    'hideTray': 'hide-tray',
    'hidePassword': 'hide-password',
    'hideMenuBar': 'hide-menu-bar',
    'hideQuit': 'hide-quit',
    'hideService_Start_Stop': 'hide-service-start-stop',
    'allow_numeric_one_time_password': 'allow-numeric-one-time-password',
    'allowHostnameAsId': 'allow-hostname-as-id',
    'disable_check_update': 'disable-check-update',
    'enable_udp_punch': 'enable-udp-punch',
    'enable_ipv6_punch': 'enable-ipv6-punch',
    'enable_file_copy_paste': 'enable-file-copy-paste',
    'sync_init_clipboard': 'sync-init-clipboard',
    'pre_elevate_service': 'pre-elevate-service',
    'allowD3dRender': 'allow-d3d-render',
    'use_texture_render': 'use-texture-render',
}

OPTION_SETTING_FIELDS = {
    'image_quality': 'image-quality',
    'custom_fps': 'custom-fps',
    'viewport': 'viewport',
    'view_style': 'view-style',
    'ui_mode': 'ui-mode',
    'unlockPin': 'unlock-pin',
    'passpolicy': 'password-policy',
}

EXTRA_BOOLEAN_FIELDS = [
    'cycleMonitor',
    'xOffline',
    'removeNewVersionNotif',
    'hide_chat_voice',
    'hide_powered_by_me',
    'addcopy',
    'disable_install',
    'no_uninstall',
    'applyprivacy',
]

TERMINAL_STATUSES = {'success', 'failure', 'cancelled', 'timed_out', 'skipped', 'action_required'}
ALLOWED_STATUS_UPDATES = TERMINAL_STATUSES | {'queued', 'in_progress', 'requested', 'waiting', 'completed'}

PLATFORM_LABELS = {
    'windows': 'Windows 64 位',
    'windows-x86': 'Windows 32 位',
    'linux': 'Linux',
    'android': 'Android',
    'macos': 'macOS',
}


def add_advanced_settings(cleaned_data, target):
    for field_name, setting_name in BOOLEAN_SETTING_FIELDS.items():
        if cleaned_data.get(field_name):
            target[setting_name] = 'Y'

    for field_name, setting_name in OPTION_SETTING_FIELDS.items():
        value = cleaned_data.get(field_name)
        if value not in (None, ''):
            target[setting_name] = str(value)


def add_manual_settings(raw_settings, target):
    for line in raw_settings.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        k, value = line.split('=', 1)
        target[k.strip()] = value.strip()


def verify_callback_token(request):
    expected = getattr(_settings, 'CALLBACK_TOKEN', '')
    if not expected:
        return True
    supplied = request.headers.get('Authorization', '').replace('Bearer ', '', 1)
    return hmac.compare_digest(supplied, expected)


def build_zip_token(filename):
    return hmac.new(
        _settings.CALLBACK_TOKEN.encode(),
        filename.encode(),
        hashlib.sha256,
    ).hexdigest()


def safe_uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError):
        raise Http404("Invalid UUID")


def generated_dir(build_uuid):
    return Path('exe') / safe_uuid(build_uuid)


def list_generated_files(build_uuid):
    directory = generated_dir(build_uuid)
    if not directory.exists():
        return []
    return sorted(
        item.name for item in directory.iterdir()
        if item.is_file() and not item.name.startswith('.')
    )


def get_latest_workflow_run(workflow_file, headers):
    time.sleep(3)
    runs_url = (
        f"https://api.github.com/repos/{_settings.GHUSER}/{_settings.REPONAME}"
        f"/actions/workflows/{workflow_file}/runs"
    )
    params = {
        "branch": _settings.GHBRANCH,
        "event": "workflow_dispatch",
        "per_page": 1,
    }
    response = requests.get(runs_url, headers=headers, params=params, timeout=20)
    if response.status_code != 200:
        return {}
    runs = response.json().get("workflow_runs", [])
    return runs[0] if runs else {}


def workflow_for_platform(platform, selfhosted=False):
    workflows = {
        'windows': 'sh-generator-windows.yml' if selfhosted else 'generator-windows.yml',
        'windows-x86': 'generator-windows-x86.yml',
        'linux': 'generator-linux.yml',
        'android': 'generator-android.yml',
        'macos': 'generator-macos.yml',
    }
    return workflows[platform]


def encode_custom_for_platform(decoded_custom, platform, theme, theme_mode):
    platform_custom = copy.deepcopy(decoded_custom)
    for settings_group in ('default-settings', 'override-settings'):
        platform_custom[settings_group].pop('theme', None)
        platform_custom[settings_group].pop('allow-darktheme', None)

    if theme != 'system':
        target_group = 'default-settings' if theme_mode == 'default' else 'override-settings'
        if platform == 'windows-x86':
            platform_custom[target_group]['allow-darktheme'] = 'Y' if theme == 'dark' else 'N'
        else:
            platform_custom[target_group]['theme'] = theme

    raw = json.dumps(platform_custom, ensure_ascii=False).encode('utf-8')
    return base64.b64encode(raw).decode('ascii')


def dispatch_platform_build(platform, version, full_url, inputs_raw, selfhosted):
    build_uuid = inputs_raw['uuid']
    workflow_file = workflow_for_platform(platform, selfhosted)
    workflow_url = (
        f"https://api.github.com/repos/{_settings.GHUSER}/{_settings.REPONAME}"
        f"/actions/workflows/{workflow_file}/dispatches"
    )
    zip_filename = f"secrets_{build_uuid}_{uuid.uuid4()}.zip"
    zip_path = Path('temp_zips') / zip_filename
    temp_json_path = Path(f"data_{uuid.uuid4()}.json")
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with temp_json_path.open('w', encoding='utf-8') as output:
            json.dump(inputs_raw, output, ensure_ascii=False)
        with pyzipper.AESZipFile(
            zip_path,
            'w',
            compression=pyzipper.ZIP_LZMA,
            encryption=pyzipper.WZ_AES,
        ) as archive:
            archive.setpassword(_settings.ZIP_PASSWORD.encode())
            archive.write(temp_json_path, arcname='secrets.json')
    finally:
        temp_json_path.unlink(missing_ok=True)

    zip_url = json.dumps({
        'url': full_url,
        'file': zip_filename,
        'token': build_zip_token(zip_filename),
    })
    data = {
        'ref': _settings.GHBRANCH,
        'inputs': {
            'version': version,
            'zip_url': zip_url,
        },
        'return_run_details': True,
    }
    headers = {
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {_settings.GHBEARER}',
        'X-GitHub-Api-Version': '2026-03-10',
    }
    job = {
        'uuid': build_uuid,
        'platform': platform,
        'platform_label': PLATFORM_LABELS[platform],
        'status': 'dispatching',
        'log_url': '',
        'error': '',
    }

    try:
        response = requests.post(workflow_url, json=data, headers=headers, timeout=30)
        if response.status_code not in (200, 204):
            zip_path.unlink(missing_ok=True)
            job['status'] = 'dispatch_failed'
            job['error'] = f"GitHub 拒绝启动任务（HTTP {response.status_code}）"
            return job

        github_data = {}
        if response.content:
            try:
                github_data = response.json()
            except ValueError:
                pass
        if not github_data.get('workflow_run_id'):
            latest_run = get_latest_workflow_run(workflow_file, headers)
            github_data['workflow_run_id'] = latest_run.get('id')
            github_data['html_url'] = latest_run.get('html_url')
        if not github_data.get('workflow_run_id'):
            job['status'] = 'dispatch_failed'
            job['error'] = 'GitHub 已接收任务，但暂时无法取得运行编号，请到 Actions 页面确认。'
            return job

        github_run = GithubRun(
            uuid=build_uuid,
            status='in_progress',
            github_run_id=github_data['workflow_run_id'],
        )
        github_run.save()
        job['status'] = 'in_progress'
        job['log_url'] = github_data.get('html_url') or (
            f"https://github.com/{_settings.GHUSER}/{_settings.REPONAME}"
            f"/actions/runs/{github_data['workflow_run_id']}"
        )
        return job
    except requests.RequestException as exc:
        zip_path.unlink(missing_ok=True)
        job['status'] = 'dispatch_failed'
        job['error'] = f'连接 GitHub 失败：{exc}'
        return job

def generator_view(request):
    if request.method == 'POST':
        form = GenerateForm(request.POST, request.FILES)
        if form.is_valid():
            user_secret = form.cleaned_data['sh_secret_field']
            selfhosted = bool(
                _settings.SH_SECRET
                and user_secret
                and hmac.compare_digest(_settings.SH_SECRET, user_secret)
            )
            platforms = form.cleaned_data['platform']
            platform = platforms[0]
            version = form.cleaned_data['version']
            delayFix = form.cleaned_data['delayFix']
            cycleMonitor = form.cleaned_data['cycleMonitor']
            xOffline = form.cleaned_data['xOffline']
            hidecm = form.cleaned_data['hidecm']
            removeNewVersionNotif = form.cleaned_data['removeNewVersionNotif']
            server = form.cleaned_data['serverIP']
            key = form.cleaned_data['key'] or form.cleaned_data['RS_PUB_KEY']
            apiServer = form.cleaned_data['apiServer']
            urlLink = form.cleaned_data['urlLink']
            downloadLink = form.cleaned_data['downloadLink']
            updateLink = form.cleaned_data['updateLink']
            if not server:
                server = 'rs-ny.rustdesk.com' #default rustdesk server
            if not key:
                key = 'OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw=' #default rustdesk key
            if not apiServer:
                apiServer = server+":21114"
            if not urlLink:
                urlLink = "https://rustdesk.com"
            if not downloadLink:
                downloadLink = "https://rustdesk.com/download"
            direction = form.cleaned_data['direction']
            installation = form.cleaned_data['installation']
            settings = form.cleaned_data['settings']
            appname = form.cleaned_data['appname']
            if not appname:
                appname = "rustdesk"
            filename = form.cleaned_data['exename']
            compname = form.cleaned_data['compname']
            if not compname:
                compname = "Purslane Ltd"
            androidappid = form.cleaned_data['androidappid']
            if not androidappid:
                androidappid = "com.carriez.flutter_hbb"
            compname = compname.replace("&","\\&")
            permPass = form.cleaned_data['permanentPassword']
            theme = form.cleaned_data['theme']
            themeDorO = form.cleaned_data['themeDorO']
            #runasadmin = form.cleaned_data['runasadmin']
            passApproveMode = form.cleaned_data['passApproveMode']
            denyLan = form.cleaned_data['denyLan']
            enableDirectIP = form.cleaned_data['enableDirectIP']
            #ipWhitelist = form.cleaned_data['ipWhitelist']
            autoClose = form.cleaned_data['autoClose']
            permissionsDorO = form.cleaned_data['permissionsDorO']
            permissionsType = form.cleaned_data['permissionsType']
            enableKeyboard = form.cleaned_data['enableKeyboard']
            enableClipboard = form.cleaned_data['enableClipboard']
            enableFileTransfer = form.cleaned_data['enableFileTransfer']
            enableAudio = form.cleaned_data['enableAudio']
            enableTCP = form.cleaned_data['enableTCP']
            enableRemoteRestart = form.cleaned_data['enableRemoteRestart']
            enableRecording = form.cleaned_data['enableRecording']
            enableBlockingInput = form.cleaned_data['enableBlockingInput']
            enableRemoteModi = form.cleaned_data['enableRemoteModi']
            removeWallpaper = form.cleaned_data['removeWallpaper']
            defaultManual = form.cleaned_data['defaultManual']
            overrideManual = form.cleaned_data['overrideManual']
            enablePrinter = form.cleaned_data['enablePrinter']
            enableCamera = form.cleaned_data['enableCamera']
            enableTerminal = form.cleaned_data['enableTerminal']

            if all(char.isascii() for char in filename):
                filename = re.sub(r'[^\w\s-]', '_', filename).strip()
                filename = filename.replace(" ","_")
            else:
                filename = "rustdesk"
            if not all(char.isascii() for char in appname):
                appname = "rustdesk"
            myuuid = str(uuid.uuid4())
            protocol = _settings.PROTOCOL
            host = request.get_host()
            full_url = f"{protocol}://{host}"
            try:
                iconfile = form.cleaned_data.get('iconfile')
                if not iconfile:
                    iconfile = form.cleaned_data.get('iconbase64')
                iconlink_url, iconlink_uuid, iconlink_file = save_png(iconfile,myuuid,full_url,"icon.png")
            except:
                print("failed to get icon, using default")
                iconlink_url = "false"
                iconlink_uuid = "false"
                iconlink_file = "false"
            try:
                logofile = form.cleaned_data.get('logofile')
                if not logofile:
                    logofile = form.cleaned_data.get('logobase64')
                logolink_url, logolink_uuid, logolink_file = save_png(logofile,myuuid,full_url,"logo.png")
            except:
                print("failed to get logo")
                logolink_url = "false"
                logolink_uuid = "false"
                logolink_file = "false"
            try:
                privacyfile = form.cleaned_data.get('privacyfile')
                if not privacyfile:
                    privacyfile = form.cleaned_data.get('privacybase64')
                privacylink_url, privacylink_uuid, privacylink_file = save_png(privacyfile,myuuid,full_url,"privacy.png")
            except:
                print("failed to get logo")
                privacylink_url = "false"
                privacylink_uuid = "false"
                privacylink_file = "false"

            ###create the custom.txt json here and send in as inputs below
            decodedCustom = {}
            if direction != "both":
                decodedCustom['conn-type'] = direction
            if installation == "installationN":
                decodedCustom['disable-installation'] = 'Y'
            if settings == "settingsN":
                decodedCustom['disable-settings'] = 'Y'
            if appname.upper() != "RUSTDESK" and appname != "":
                decodedCustom['app-name'] = appname
            decodedCustom['override-settings'] = {}
            decodedCustom['default-settings'] = {}
            if permPass != "":
                decodedCustom['password'] = permPass
            if theme != "system":
                if themeDorO == "default":
                    if platform == "windows-x86":
                        decodedCustom['default-settings']['allow-darktheme'] = 'Y' if theme == "dark" else 'N'
                    else:
                        decodedCustom['default-settings']['theme'] = theme
                elif themeDorO == "override":
                    if platform == "windows-x86":
                        decodedCustom['override-settings']['allow-darktheme'] = 'Y' if theme == "dark" else 'N'
                    else:
                        decodedCustom['override-settings']['theme'] = theme
            decodedCustom['enable-lan-discovery'] = 'N' if denyLan else 'Y'
            #decodedCustom['direct-server'] = 'Y' if enableDirectIP else 'N'
            decodedCustom['allow-auto-disconnect'] = 'Y' if autoClose else 'N'
            if permissionsDorO == "default":
                decodedCustom['default-settings']['access-mode'] = permissionsType
                decodedCustom['default-settings']['enable-keyboard'] = 'Y' if enableKeyboard else 'N'
                decodedCustom['default-settings']['enable-clipboard'] = 'Y' if enableClipboard else 'N'
                decodedCustom['default-settings']['enable-file-transfer'] = 'Y' if enableFileTransfer else 'N'
                decodedCustom['default-settings']['enable-audio'] = 'Y' if enableAudio else 'N'
                decodedCustom['default-settings']['enable-tunnel'] = 'Y' if enableTCP else 'N'
                decodedCustom['default-settings']['enable-remote-restart'] = 'Y' if enableRemoteRestart else 'N'
                decodedCustom['default-settings']['enable-record-session'] = 'Y' if enableRecording else 'N'
                decodedCustom['default-settings']['enable-block-input'] = 'Y' if enableBlockingInput else 'N'
                decodedCustom['default-settings']['allow-remote-config-modification'] = 'Y' if enableRemoteModi else 'N'
                decodedCustom['default-settings']['direct-server'] = 'Y' if enableDirectIP else 'N'
                decodedCustom['default-settings']['verification-method'] = 'use-permanent-password' if hidecm else 'use-both-passwords'
                decodedCustom['default-settings']['approve-mode'] = passApproveMode
                decodedCustom['default-settings']['allow-hide-cm'] = 'Y' if hidecm else 'N'
                decodedCustom['default-settings']['allow-remove-wallpaper'] = 'Y' if removeWallpaper else 'N'
                decodedCustom['default-settings']['enable-remote-printer'] = 'Y' if enablePrinter else 'N'
                decodedCustom['default-settings']['enable-camera'] = 'Y' if enableCamera else 'N'
                decodedCustom['default-settings']['enable-terminal'] = 'Y' if enableTerminal else 'N'
                add_advanced_settings(form.cleaned_data, decodedCustom['default-settings'])
            else:
                decodedCustom['override-settings']['access-mode'] = permissionsType
                decodedCustom['override-settings']['enable-keyboard'] = 'Y' if enableKeyboard else 'N'
                decodedCustom['override-settings']['enable-clipboard'] = 'Y' if enableClipboard else 'N'
                decodedCustom['override-settings']['enable-file-transfer'] = 'Y' if enableFileTransfer else 'N'
                decodedCustom['override-settings']['enable-audio'] = 'Y' if enableAudio else 'N'
                decodedCustom['override-settings']['enable-tunnel'] = 'Y' if enableTCP else 'N'
                decodedCustom['override-settings']['enable-remote-restart'] = 'Y' if enableRemoteRestart else 'N'
                decodedCustom['override-settings']['enable-record-session'] = 'Y' if enableRecording else 'N'
                decodedCustom['override-settings']['enable-block-input'] = 'Y' if enableBlockingInput else 'N'
                decodedCustom['override-settings']['allow-remote-config-modification'] = 'Y' if enableRemoteModi else 'N'
                decodedCustom['override-settings']['direct-server'] = 'Y' if enableDirectIP else 'N'
                decodedCustom['override-settings']['verification-method'] = 'use-permanent-password' if hidecm else 'use-both-passwords'
                decodedCustom['override-settings']['approve-mode'] = passApproveMode
                decodedCustom['override-settings']['allow-hide-cm'] = 'Y' if hidecm else 'N'
                decodedCustom['override-settings']['allow-remove-wallpaper'] = 'Y' if removeWallpaper else 'N'
                decodedCustom['override-settings']['enable-remote-printer'] = 'Y' if enablePrinter else 'N'
                decodedCustom['override-settings']['enable-camera'] = 'Y' if enableCamera else 'N'
                decodedCustom['override-settings']['enable-terminal'] = 'Y' if enableTerminal else 'N'
                add_advanced_settings(form.cleaned_data, decodedCustom['override-settings'])

            add_manual_settings(defaultManual, decodedCustom['default-settings'])
            add_manual_settings(overrideManual, decodedCustom['override-settings'])
            
            jobs = []
            for index, selected_platform in enumerate(platforms):
                build_uuid = myuuid if index == 0 else str(uuid.uuid4())
                inputs_raw = {
                    'server': server,
                    'key': key,
                    'apiServer': apiServer,
                    'custom': encode_custom_for_platform(
                        decodedCustom,
                        selected_platform,
                        theme,
                        themeDorO,
                    ),
                    'uuid': build_uuid,
                    'iconlink_url': iconlink_url,
                    'iconlink_uuid': iconlink_uuid,
                    'iconlink_file': iconlink_file,
                    'logolink_url': logolink_url,
                    'logolink_uuid': logolink_uuid,
                    'logolink_file': logolink_file,
                    'privacylink_url': privacylink_url,
                    'privacylink_uuid': privacylink_uuid,
                    'privacylink_file': privacylink_file,
                    'appname': appname,
                    'genurl': _settings.GENURL,
                    'urlLink': urlLink,
                    'downloadLink': downloadLink,
                    'updateLink': updateLink,
                    'delayFix': 'true' if delayFix else 'false',
                    'rdgen': 'true',
                    'cycleMonitor': 'true' if cycleMonitor else 'false',
                    'xOffline': 'true' if xOffline else 'false',
                    'removeNewVersionNotif': 'true' if removeNewVersionNotif else 'false',
                    'compname': compname,
                    'androidappid': androidappid,
                    'filename': filename,
                    'token': _settings.CALLBACK_TOKEN,
                }
                for field_name in EXTRA_BOOLEAN_FIELDS:
                    inputs_raw[field_name] = (
                        'true' if form.cleaned_data.get(field_name) else 'false'
                    )
                jobs.append(dispatch_platform_build(
                    selected_platform,
                    version,
                    full_url,
                    inputs_raw,
                    selfhosted,
                ))

            if len(jobs) == 1 and jobs[0]['status'] == 'in_progress':
                job = jobs[0]
                return render(request, 'waiting.html', {
                    'filename': filename,
                    'uuid': job['uuid'],
                    'status': '构建已启动，请稍候',
                    'platform': job['platform'],
                    'log_url': job['log_url'],
                })
            return render(request, 'batch_waiting.html', {
                'filename': filename,
                'jobs': jobs,
            })
    else:
        form = GenerateForm()
    #return render(request, 'maintenance.html')
    return render(request, 'generator.html', {'form': form})


from django.shortcuts import render, get_object_or_404
from django.db.models import Q


def refresh_github_run(gh_run):
    if gh_run.status in TERMINAL_STATUSES or not gh_run.github_run_id:
        return gh_run
    headers = {
        'Authorization': f'Bearer {_settings.GHBEARER}',
        'Accept': 'application/vnd.github+json',
    }
    api_url = (
        f"https://api.github.com/repos/{_settings.GHUSER}/{_settings.REPONAME}"
        f"/actions/runs/{gh_run.github_run_id}"
    )
    try:
        response = requests.get(api_url, headers=headers, timeout=20)
        if response.status_code == 200:
            github_data = response.json()
            new_status = github_data.get('status', gh_run.status)
            if new_status == 'completed':
                new_status = github_data.get('conclusion') or 'failure'
            if new_status != gh_run.status:
                gh_run.status = new_status
                gh_run.save(update_fields=['status'])
    except requests.RequestException as exc:
        print(f'Error checking GitHub run {gh_run.github_run_id}: {exc}')
    return gh_run


def check_for_file(request):
    filename = request.GET.get('filename')
    uuid = safe_uuid(request.GET.get('uuid'))
    platform = request.GET.get('platform')
    gh_run = get_object_or_404(GithubRun, uuid=uuid)
    github_log_url = f"https://github.com/{_settings.GHUSER}/{_settings.REPONAME}/actions/runs/{gh_run.github_run_id}"
    gh_run = refresh_github_run(gh_run)
    
    if gh_run.status == "success":
        return render(request, 'generated.html', {
            'filename': filename, 
            'uuid': uuid, 
            'platform': platform,
            'files': list_generated_files(uuid),
        })
        
    elif gh_run.status in ['failure', 'cancelled', 'timed_out', 'skipped', 'action_required']:
        return render(request, 'failure.html', {
            'log_url': github_log_url, 
            'filename': filename, 
            'uuid': uuid, 
            'platform': platform,
            'status': gh_run.status
        })
        
    else:
        return render(request, 'waiting.html', {
            'filename': filename, 
            'uuid': uuid, 
            'status': gh_run.status, 
            'platform': platform, 
            'log_url': github_log_url
        })


def build_status(request):
    build_uuid = safe_uuid(request.GET.get('uuid'))
    gh_run = get_object_or_404(GithubRun, uuid=build_uuid)
    gh_run = refresh_github_run(gh_run)
    files = list_generated_files(build_uuid) if gh_run.status == 'success' else []
    return JsonResponse({
        'uuid': build_uuid,
        'status': gh_run.status,
        'terminal': gh_run.status in TERMINAL_STATUSES,
        'files': files,
        'log_url': (
            f"https://github.com/{_settings.GHUSER}/{_settings.REPONAME}"
            f"/actions/runs/{gh_run.github_run_id}"
        ),
    })

def download(request):
    filename = os.path.basename(request.GET['filename'])
    build_uuid = safe_uuid(request.GET.get('uuid'))
    get_object_or_404(GithubRun, uuid=build_uuid, status='success')
    if filename not in list_generated_files(build_uuid):
        raise Http404("File not found")
    file_path = generated_dir(build_uuid) / filename
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename, content_type=content_type)

def get_png(request):
    filename = os.path.basename(request.GET['filename'])
    uuid = safe_uuid(request.GET['uuid'])
    #filename = filename+".exe"
    file_path = os.path.join('png',uuid,filename)
    with open(file_path, 'rb') as file:
        response = HttpResponse(file, headers={
            'Content-Type': 'image/png',
            'Content-Disposition': f'attachment; filename="{filename}"'
        })

    return response

def create_github_run(myuuid):
    new_github_run = GithubRun(
        uuid=myuuid,
        status="Starting generator...please wait"
    )
    new_github_run.save()

@csrf_exempt
@require_POST
def update_github_run(request):
    if not verify_callback_token(request):
        return HttpResponse("Unauthorized", status=401)
    data = json.loads(request.body)
    myuuid = data.get('uuid')
    mystatus = data.get('status')
    if mystatus not in ALLOWED_STATUS_UPDATES:
        return HttpResponse("Invalid status", status=400)
    GithubRun.objects.filter(Q(uuid=safe_uuid(myuuid))).update(status=mystatus)
    return HttpResponse('')

def resize_and_encode_icon(imagefile):
    maxWidth = 200
    try:
        with io.BytesIO() as image_buffer:
            for chunk in imagefile.chunks():
                image_buffer.write(chunk)
            image_buffer.seek(0)

            img = Image.open(image_buffer)
            imgcopy = img.copy()
    except (IOError, OSError):
        raise ValueError("Uploaded file is not a valid image format.")

    # Check if resizing is necessary
    if img.size[0] <= maxWidth:
        with io.BytesIO() as image_buffer:
            imgcopy.save(image_buffer, format=imagefile.content_type.split('/')[1])
            image_buffer.seek(0)
            return_image = ContentFile(image_buffer.read(), name=imagefile.name)
        return base64.b64encode(return_image.read())

    # Calculate resized height based on aspect ratio
    wpercent = (maxWidth / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))

    # Resize the image while maintaining aspect ratio using LANCZOS resampling
    imgcopy = imgcopy.resize((maxWidth, hsize), Image.Resampling.LANCZOS)

    with io.BytesIO() as resized_image_buffer:
        imgcopy.save(resized_image_buffer, format=imagefile.content_type.split('/')[1])
        resized_image_buffer.seek(0)

        resized_imagefile = ContentFile(resized_image_buffer.read(), name=imagefile.name)

    # Return the Base64 encoded representation of the resized image
    resized64 = base64.b64encode(resized_imagefile.read())
    #print(resized64)
    return resized64
 
#the following is used when accessed from an external source, like the rustdesk api server
@csrf_exempt
@require_POST
def startgh(request):
    if not verify_callback_token(request):
        return HttpResponse("Unauthorized", status=401)
    #print(request)
    data_ = json.loads(request.body)
    ####from here run the github action, we need user, repo, access token.
    url = 'https://api.github.com/repos/'+_settings.GHUSER+'/'+_settings.REPONAME+'/actions/workflows/generator-'+data_.get('platform')+'.yml/dispatches'  
    data = {
        "ref": _settings.GHBRANCH,
        "inputs":{
            "server":data_.get('server'),
            "key":data_.get('key'),
            "apiServer":data_.get('apiServer'),
            "custom":data_.get('custom'),
            "uuid":data_.get('uuid'),
            "iconlink":data_.get('iconlink'),
            "logolink":data_.get('logolink'),
            "appname":data_.get('appname'),
            "extras":data_.get('extras'),
            "filename":data_.get('filename')
        }
    } 
    headers = {
        'Accept':  'application/vnd.github+json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer '+_settings.GHBEARER,
        'X-GitHub-Api-Version': '2026-03-10'
    }
    response = requests.post(url, json=data, headers=headers)
    print(response)
    return HttpResponse(status=204)

def save_png(file, uuid, domain, name):
    file_save_path = "png/%s/%s" % (uuid, name)
    Path("png/%s" % uuid).mkdir(parents=True, exist_ok=True)

    if isinstance(file, str):  # Check if it's a base64 string
        try:
            header, encoded = file.split(';base64,')
            decoded_img = base64.b64decode(encoded)
            file = ContentFile(decoded_img, name=name) # Create a file-like object
        except ValueError:
            print("Invalid base64 data")
            return None  # Or handle the error as you see fit
        except Exception as e:  # Catch general exceptions during decoding
            print(f"Error decoding base64: {e}")
            return None
        
    with open(file_save_path, "wb+") as f:
        for chunk in file.chunks():
            f.write(chunk)
    # imageJson = {}
    # imageJson['url'] = domain
    # imageJson['uuid'] = uuid
    # imageJson['file'] = name
    #return "%s/%s" % (domain, file_save_path)
    return domain, uuid, name

@csrf_exempt
@require_POST
def save_custom_client(request):
    if not verify_callback_token(request):
        return HttpResponse("Unauthorized", status=401)
    if 'file' not in request.FILES or not request.POST.get('uuid'):
        return HttpResponse("Missing file or uuid", status=400)
    file = request.FILES['file']
    myuuid = safe_uuid(request.POST.get('uuid'))
    if not GithubRun.objects.filter(uuid=myuuid).exists():
        return HttpResponse("Unknown build UUID", status=404)
    file_save_path = "exe/%s/%s" % (myuuid, os.path.basename(file.name))
    Path("exe/%s" % myuuid).mkdir(parents=True, exist_ok=True)
    with open(file_save_path, "wb+") as f:
        for chunk in file.chunks():
            f.write(chunk)

    return HttpResponse("File saved successfully!")

@csrf_exempt
@require_POST
def cleanup_secrets(request):
    if not verify_callback_token(request):
        return HttpResponse("Unauthorized", status=401)
    # Pass the UUID as a query param or in JSON body
    data = json.loads(request.body)
    my_uuid = data.get('uuid')
    
    if not my_uuid:
        return HttpResponse("Missing UUID", status=400)

    # 1. Find the files in your temp directory matching the UUID
    temp_dir = os.path.join('temp_zips')
    
    # We look for any file starting with 'secrets_' and containing the uuid
    for filename in os.listdir(temp_dir):
        if my_uuid in filename and filename.endswith('.zip'):
            file_path = os.path.join(temp_dir, filename)
            try:
                os.remove(file_path)
                print(f"Successfully deleted {file_path}")
            except OSError as e:
                print(f"Error deleting file: {e}")

    return HttpResponse("Cleanup successful", status=200)

def get_zip(request):
    filename = os.path.basename(request.GET['filename'])
    token = request.GET.get('token', '')
    if not hmac.compare_digest(token, build_zip_token(filename)):
        return HttpResponse("Unauthorized", status=401)
    #filename = filename+".exe"
    file_path = os.path.join('temp_zips',filename)
    if not os.path.exists(file_path):
        raise Http404("Zip not found")
    with open(file_path, 'rb') as file:
        response = HttpResponse(file, headers={
            'Content-Type': 'application/zip',
            'Content-Disposition': f'attachment; filename="{filename}"'
        })

    return response
