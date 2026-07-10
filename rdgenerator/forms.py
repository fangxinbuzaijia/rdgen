from django import forms
from PIL import Image

MAX_IMAGE_BYTES = 5 * 1024 * 1024

class GenerateForm(forms.Form):
    sh_secret_field = forms.CharField(required=False)
    #Platform
    platform = forms.ChoiceField(choices=[('windows','Windows 64 位'),('windows-x86','Windows 32 位'),('linux','Linux'),('android','Android'),('macos','macOS')], initial='windows')
    version = forms.ChoiceField(choices=[('master','nightly'),('1.4.8','1.4.8'),('1.4.7','1.4.7'),('1.4.6','1.4.6'),('1.4.5','1.4.5'),('1.4.4','1.4.4'),('1.4.3','1.4.3'),('1.4.2','1.4.2'),('1.4.1','1.4.1'),('1.4.0','1.4.0'),('1.3.9','1.3.9'),('1.3.8','1.3.8'),('1.3.7','1.3.7'),('1.3.6','1.3.6'),('1.3.5','1.3.5'),('1.3.4','1.3.4'),('1.3.3','1.3.3')], initial='1.4.8')
    help_text="'master' 是开发版，功能最新但稳定性可能较低"
    delayFix = forms.BooleanField(initial=True, required=False)

    #General
    exename = forms.CharField(label="Name for EXE file", required=True)
    appname = forms.CharField(label="Custom App Name", required=False)
    direction = forms.ChoiceField(widget=forms.RadioSelect, choices=[
        ('incoming', '仅允许被控'),
        ('outgoing', '仅允许主控'),
        ('both', '双向连接')
    ], initial='both')
    installation = forms.ChoiceField(label="Disable Installation", choices=[
        ('installationY', '允许安装'),
        ('installationN', '禁用安装')
    ], initial='installationY')
    settings = forms.ChoiceField(label="Disable Settings", choices=[
        ('settingsY', '允许打开设置'),
        ('settingsN', '禁用设置')
    ], initial='settingsY')
    androidappid = forms.CharField(label="Custom Android App ID (replaces 'com.carriez.flutter_hbb')", required=False)

    #Custom Server
    serverIP = forms.CharField(label="Host", required=False)
    apiServer = forms.CharField(label="API Server", required=False)
    key = forms.CharField(label="Key", required=False)
    RS_PUB_KEY = forms.CharField(label="RS Pub Key", required=False)
    urlLink = forms.CharField(label="Custom URL for links", required=False)
    downloadLink = forms.CharField(label="Custom URL for downloading new versions", required=False)
    updateLink = forms.CharField(label="Custom URL for online updates", required=False)
    compname = forms.CharField(label="Company name",required=False)

    #Visual
    iconfile = forms.FileField(label="Custom App Icon (in .png format)", required=False, widget=forms.FileInput(attrs={'accept': 'image/png'}))
    logofile = forms.FileField(label="Custom App Logo (in .png format)", required=False, widget=forms.FileInput(attrs={'accept': 'image/png'}))
    privacyfile = forms.FileField(label="Custom privacy screen (in .png format)", required=False, widget=forms.FileInput(attrs={'accept': 'image/png'}))
    iconbase64 = forms.CharField(required=False)
    logobase64 = forms.CharField(required=False)
    privacybase64 = forms.CharField(required=False)
    theme = forms.ChoiceField(choices=[
        ('light', '浅色'),
        ('dark', '深色'),
        ('system', '跟随系统')
    ], initial='system')
    themeDorO = forms.ChoiceField(choices=[('default', '默认'),('override', '强制覆盖')], initial='default')

    #Security
    passApproveMode = forms.ChoiceField(choices=[('password','通过密码接受连接'),('click','通过点击接受连接'),('password-click','密码或点击均可')],initial='password-click')
    permanentPassword = forms.CharField(widget=forms.PasswordInput(), required=False)
    unlockPin = forms.CharField(widget=forms.PasswordInput(), required=False)
    passpolicy = forms.CharField(required=False)
    #runasadmin = forms.ChoiceField(choices=[('false','No'),('true','Yes')], initial='false')
    denyLan = forms.BooleanField(initial=False, required=False)
    enableDirectIP = forms.BooleanField(initial=False, required=False)
    #ipWhitelist = forms.BooleanField(initial=False, required=False)
    autoClose = forms.BooleanField(initial=False, required=False)
    hideSecuritySettings = forms.BooleanField(initial=False, required=False)
    hideNetworkSettings = forms.BooleanField(initial=False, required=False)
    hideServerSettings = forms.BooleanField(initial=False, required=False)
    hideRemotePrinterSettings = forms.BooleanField(initial=False, required=False)
    hide_account = forms.BooleanField(initial=False, required=False)
    remove_preset_password_warning = forms.BooleanField(initial=False, required=False)
    hideProxySettings = forms.BooleanField(initial=False, required=False)
    hideWebsocketSettings = forms.BooleanField(initial=False, required=False)

    #Permissions
    permissionsDorO = forms.ChoiceField(choices=[('default', '默认设置'),('override', '强制覆盖')], initial='default')
    permissionsType = forms.ChoiceField(choices=[('custom', '自定义'),('full', '完全控制'),('view','仅屏幕共享')], initial='custom')
    enableKeyboard =  forms.BooleanField(initial=True, required=False)
    enableClipboard = forms.BooleanField(initial=True, required=False)
    enableFileTransfer = forms.BooleanField(initial=True, required=False)
    enableAudio = forms.BooleanField(initial=True, required=False)
    enableTCP = forms.BooleanField(initial=True, required=False)
    enableRemoteRestart = forms.BooleanField(initial=True, required=False)
    enableRecording = forms.BooleanField(initial=True, required=False)
    enableBlockingInput = forms.BooleanField(initial=True, required=False)
    enableRemoteModi = forms.BooleanField(initial=False, required=False)
    hidecm = forms.BooleanField(initial=False, required=False)
    enablePrinter = forms.BooleanField(initial=True, required=False)
    enableCamera = forms.BooleanField(initial=True, required=False)
    enableTerminal = forms.BooleanField(initial=True, required=False)

    #Other
    removeWallpaper = forms.BooleanField(initial=True, required=False)
    image_quality = forms.ChoiceField(choices=[
        ('', '默认'),
        ('low', '低'),
        ('balanced', '均衡'),
        ('best', '最佳')
    ], required=False)
    custom_fps = forms.IntegerField(min_value=0, max_value=120, required=False)
    viewport = forms.ChoiceField(choices=[
        ('', '默认'),
        ('adaptive', '自适应'),
        ('original', '原始尺寸'),
        ('stretch', '拉伸')
    ], required=False)
    view_style = forms.ChoiceField(choices=[
        ('', '默认'),
        ('scroll', '滚动'),
        ('shrink', '缩放适应'),
        ('stretch', '拉伸')
    ], required=False)
    ui_mode = forms.ChoiceField(choices=[
        ('', '默认'),
        ('classic', '经典'),
        ('new', '新版')
    ], required=False)
    viewOnly = forms.BooleanField(initial=False, required=False)
    collapse_toolbar = forms.BooleanField(initial=False, required=False)
    privacy_mode = forms.BooleanField(initial=False, required=False)
    privacy_wallpaper = forms.BooleanField(initial=False, required=False)
    hide_username_on_card = forms.BooleanField(initial=False, required=False)
    hide_chat_voice = forms.BooleanField(initial=False, required=False)
    hide_sensitive_ui = forms.BooleanField(initial=False, required=False)
    hideTray = forms.BooleanField(initial=False, required=False)
    hidePassword = forms.BooleanField(initial=False, required=False)
    hideMenuBar = forms.BooleanField(initial=False, required=False)
    hideQuit = forms.BooleanField(initial=False, required=False)
    hideService_Start_Stop = forms.BooleanField(initial=False, required=False)
    addcopy = forms.BooleanField(initial=False, required=False)
    disable_install = forms.BooleanField(initial=False, required=False)
    no_uninstall = forms.BooleanField(initial=False, required=False)
    allowD3dRender = forms.BooleanField(initial=False, required=False)
    use_texture_render = forms.BooleanField(initial=False, required=False)
    pre_elevate_service = forms.BooleanField(initial=False, required=False)
    sync_init_clipboard = forms.BooleanField(initial=False, required=False)
    hide_powered_by_me = forms.BooleanField(initial=False, required=False)
    enable_udp_punch = forms.BooleanField(initial=False, required=False)
    enable_ipv6_punch = forms.BooleanField(initial=False, required=False)
    enable_file_copy_paste = forms.BooleanField(initial=False, required=False)
    allow_numeric_one_time_password = forms.BooleanField(initial=False, required=False)
    allowHostnameAsId = forms.BooleanField(initial=False, required=False)
    applyprivacy = forms.BooleanField(initial=False, required=False)
    disable_check_update = forms.BooleanField(initial=False, required=False)

    defaultManual = forms.CharField(widget=forms.Textarea, required=False)
    overrideManual = forms.CharField(widget=forms.Textarea, required=False)

    #custom added features
    cycleMonitor = forms.BooleanField(initial=False, required=False)
    xOffline = forms.BooleanField(initial=False, required=False)
    removeNewVersionNotif = forms.BooleanField(initial=False, required=False)

    def validate_png(self, image, field_name, require_square=False):
        if image:
            try:
                if image.size > MAX_IMAGE_BYTES:
                    raise forms.ValidationError(f"{field_name} must be smaller than 5 MB.")
                img = Image.open(image)
                if img.format != 'PNG':
                    raise forms.ValidationError(f"{field_name} only supports PNG images.")

                width, height = img.size
                if require_square and width != height:
                    raise forms.ValidationError(f"{field_name} dimensions must be square.")

                image.seek(0)
                return image
            except OSError:
                raise forms.ValidationError(f"Invalid {field_name}.")
            except Exception as e:
                raise forms.ValidationError(f"Error processing {field_name}: {e}")
        return image

    def clean_iconfile(self):
        return self.validate_png(self.cleaned_data['iconfile'], "Custom App Icon", True)

    def clean_logofile(self):
        return self.validate_png(self.cleaned_data['logofile'], "Custom App Logo")

    def clean_privacyfile(self):
        return self.validate_png(self.cleaned_data['privacyfile'], "Custom privacy screen")
