import base64
import json
import uuid
from unittest.mock import patch

from django.test import TestCase

from .forms import GenerateForm
from .models import GithubRun
from .views import encode_custom_for_platform


class MultiPlatformFormTests(TestCase):
    def test_platform_field_accepts_multiple_values(self):
        form = GenerateForm(data={'platform': ['windows', 'linux']})
        form.is_valid()
        self.assertNotIn('platform', form.errors)

    def test_platform_field_requires_at_least_one_value(self):
        form = GenerateForm(data={'platform': []})
        form.is_valid()
        self.assertIn('platform', form.errors)

    def test_duplicate_platform_values_are_deduplicated(self):
        form = GenerateForm(data={'platform': ['windows', 'windows', 'linux']})
        form.is_valid()
        self.assertEqual(form.cleaned_data['platform'], ['windows', 'linux'])


class PlatformCustomSettingsTests(TestCase):
    def decode(self, value):
        return json.loads(base64.b64decode(value).decode('utf-8'))

    def test_windows_x86_uses_legacy_dark_theme_key(self):
        custom = {'default-settings': {}, 'override-settings': {}}
        result = self.decode(encode_custom_for_platform(custom, 'windows-x86', 'dark', 'default'))
        self.assertEqual(result['default-settings']['allow-darktheme'], 'Y')
        self.assertNotIn('theme', result['default-settings'])

    def test_other_platforms_use_theme_key(self):
        custom = {'default-settings': {}, 'override-settings': {}}
        result = self.decode(encode_custom_for_platform(custom, 'linux', 'dark', 'default'))
        self.assertEqual(result['default-settings']['theme'], 'dark')
        self.assertNotIn('allow-darktheme', result['default-settings'])


class MultiPlatformBuildViewTests(TestCase):
    @patch('rdgenerator.views.save_png', return_value=('false', 'false', 'false'))
    @patch('rdgenerator.views.dispatch_platform_build')
    def test_one_submission_dispatches_each_selected_platform(self, dispatch, _save_png):
        def fake_dispatch(platform, _version, _full_url, inputs_raw, _selfhosted):
            return {
                'uuid': inputs_raw['uuid'],
                'platform': platform,
                'platform_label': platform,
                'status': 'in_progress',
                'log_url': f'https://example.test/{platform}',
                'error': '',
            }

        dispatch.side_effect = fake_dispatch
        response = self.client.post('/generator', data={
            'platform': ['windows', 'linux'],
            'version': '1.4.8',
            'exename': 'company-client',
            'direction': 'both',
            'installation': 'installationY',
            'settings': 'settingsY',
            'theme': 'system',
            'themeDorO': 'default',
            'passApproveMode': 'password-click',
            'permissionsDorO': 'default',
            'permissionsType': 'custom',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'batch_waiting.html')
        self.assertEqual(dispatch.call_count, 2)
        first_uuid = dispatch.call_args_list[0].args[3]['uuid']
        second_uuid = dispatch.call_args_list[1].args[3]['uuid']
        self.assertNotEqual(first_uuid, second_uuid)
        uuid.UUID(first_uuid)
        uuid.UUID(second_uuid)


class BuildStatusTests(TestCase):
    def test_status_endpoint_returns_terminal_state(self):
        build_uuid = str(uuid.uuid4())
        GithubRun.objects.create(
            id=1,
            uuid=build_uuid,
            status='success',
            github_run_id=123456,
        )
        response = self.client.get('/build_status', {'uuid': build_uuid})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['terminal'])
        self.assertEqual(response.json()['status'], 'success')
