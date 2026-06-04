import json
import os
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.dashboard.views import (
    _build_bigmodel_context_payload,
    _build_bigmodel_messages,
    _build_question_profile,
    _get_bigmodel_request_plan,
    _clean_ai_output,
    _extract_bigmodel_result,
    _format_sse_event,
    _iter_sse_payloads,
    _stream_bigmodel_events,
)


class DashboardAiHelperTests(SimpleTestCase):
    def test_clean_ai_output_removes_control_tokens_and_placeholders(self):
        cleaned, meta = _clean_ai_output(
            "<think>内部推理</think>\n"
            "待补充：这里不应该展示\n"
            "【结论】\n"
            "- DO 偏低，需要优先增氧。\n"
            "<|assistant|>"
        )

        self.assertEqual(cleaned, "【结论】\n- DO 偏低，需要优先增氧。")
        self.assertGreaterEqual(meta['placeholder_hits'], 1)

    def test_extract_bigmodel_result_prefers_final_answer_over_reasoning(self):
        result = _extract_bigmodel_result(
            {
                'choices': [
                    {
                        'finish_reason': 'stop',
                        'message': {
                            'content': '【结论】\n- 断面 A 风险最高。',
                            'reasoning_content': '这是模型内部推理，不该直接展示。',
                        },
                    }
                ],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 20},
            },
            log_id='unit-test-log',
            attempts=1,
            token_budget=1536,
        )

        self.assertEqual(result['answer'], "【结论】\n- 断面 A 风险最高。")
        self.assertEqual(result['reasoning'], "这是模型内部推理，不该直接展示。")
        self.assertEqual(result['finish_reason'], 'stop')
        self.assertFalse(result['truncated'])

    def test_build_bigmodel_context_payload_compacts_sensor_fields(self):
        payload, stats = _build_bigmodel_context_payload(
            {
                'summary': {'total_devices': 2},
                'question_profile': {
                    'intent': 'oxygen',
                    'focus_metrics': ['dissolved_oxygen'],
                    'output_hint': '优先分析溶解氧风险与增氧处置顺序。',
                },
                'sensors': [
                    {
                        'station_id': 'A001',
                        'station_name': '一号塘口',
                        'province': '江苏省',
                        'city': '苏州市',
                        'water_quality': 'Ⅳ',
                        'risk_score': 5,
                        'timestamp': '2026-05-21T09:58:00+08:00',
                        'dissolved_oxygen': 4.2,
                        'ph': 7.1,
                        'temperature': 28.6,
                        'total_phosphorus': 0.123,
                        'algae_density': 12345,
                    }
                ],
            }
        )

        self.assertEqual(stats['sensor_count'], 1)
        self.assertEqual(payload['sensors'][0]['station_name'], '一号塘口')
        self.assertIn('dissolved_oxygen', payload['sensors'][0])
        self.assertNotIn('algae_density', payload['sensors'][0])

    def test_get_bigmodel_request_plan_prefers_stream_defaults(self):
        plan = _get_bigmodel_request_plan({'intent': 'oxygen'})

        self.assertEqual(plan['thinking_type'], 'disabled')
        self.assertEqual(plan['max_attempts'], 1)
        self.assertEqual(plan['timeout_seconds'], 45)
        self.assertLessEqual(plan['max_tokens'], 640)

    def test_build_question_profile_marks_smalltalk_and_uses_plain_messages(self):
        profile = _build_question_profile('hello')
        messages, _stats, _plan = _build_bigmodel_messages(
            'hello',
            {
                'question_profile': profile,
                'summary': {'total_devices': 2},
                'sensors': [{'station_id': 'A001', 'station_name': '一号塘口'}],
            },
        )

        self.assertEqual(profile['intent'], 'smalltalk')
        self.assertEqual(profile['focus_metrics'], [])
        self.assertEqual(messages[1]['content'], 'hello')
        self.assertNotIn('上下文数据(JSON)', messages[1]['content'])

    def test_format_sse_event_emits_event_and_json_data(self):
        payload = _format_sse_event('chunk', {'delta': '风险上升'})

        self.assertEqual(payload, 'event: chunk\ndata: {"delta": "风险上升"}\n\n')

    def test_iter_sse_payloads_parses_multiple_blocks(self):
        chunks = [
            'event: meta',
            'data: {"model":"glm-5.1"}',
            '',
            'event: chunk',
            'data: {"delta":"【结论】"}',
            '',
            'data: [DONE]',
            '',
        ]

        events = list(_iter_sse_payloads(chunks))

        self.assertEqual(events, [
            ('meta', '{"model":"glm-5.1"}'),
            ('chunk', '{"delta":"【结论】"}'),
            ('message', '[DONE]'),
        ])

    @patch('apps.dashboard.views._call_bigmodel')
    @patch('apps.dashboard.views.requests.post')
    @patch('apps.dashboard.views._build_bigmodel_messages')
    def test_stream_bigmodel_events_returns_partial_answer_when_truncated(
        self,
        mock_build_messages,
        mock_post,
        mock_call_bigmodel,
    ):
        mock_build_messages.return_value = (
            [{'role': 'user', 'content': '哪些断面需要优先处理？'}],
            {
                'sensor_count': 10,
                'sensor_limit': 10,
                'province_sensor_count': 0,
                'province_sensor_limit': 8,
            },
            {
                'max_tokens': 640,
                'timeout_seconds': 45,
                'thinking_type': 'disabled',
                'max_attempts': 1,
            },
        )
        mock_call_bigmodel.side_effect = RuntimeError('repair failed')

        class FakeStreamResponse:
            status_code = 200
            headers = {'x-log-id': 'stream-unit-test'}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def iter_lines(self, decode_unicode=True):
                return iter([
                    'data: {"choices":[{"delta":{"content":"【结论】\\n"}}]}',
                    '',
                    'data: {"choices":[{"delta":{"content":"- 保留已生成的部分回答。"},"finish_reason":"length"}],"usage":{"completion_tokens":24}}',
                    '',
                    'data: [DONE]',
                    '',
                ])

        mock_post.return_value = FakeStreamResponse()

        state = {}
        events = list(_stream_bigmodel_events('unit-test-key', 'glm-5.1', '哪些断面需要优先处理？', {}, state))

        self.assertEqual(len(events), 3)
        self.assertIn('event: chunk', events[0])
        self.assertIn('event: chunk', events[1])
        self.assertIn('event: done', events[2])
        self.assertIn('"truncated": true', events[2])
        self.assertIn('"degraded": true', events[2])
        self.assertEqual(state['answer'], '【结论】\n- 保留已生成的部分回答。')
        self.assertTrue(state['truncated'])

    @patch('apps.dashboard.views._call_bigmodel')
    @patch('apps.dashboard.views.requests.post')
    @patch('apps.dashboard.views._build_bigmodel_messages')
    def test_stream_bigmodel_events_repairs_truncated_answer_with_followup_call(
        self,
        mock_build_messages,
        mock_post,
        mock_call_bigmodel,
    ):
        mock_build_messages.return_value = (
            [{'role': 'user', 'content': '哪些断面需要优先处理？'}],
            {
                'sensor_count': 10,
                'sensor_limit': 10,
                'province_sensor_count': 0,
                'province_sensor_limit': 8,
            },
            {
                'max_tokens': 896,
                'timeout_seconds': 45,
                'thinking_type': 'disabled',
                'max_attempts': 1,
            },
        )
        mock_call_bigmodel.return_value = {
            'answer': '【结论】\n- 黄竹尾水闸、杨洼闸、挖沟泵站需要优先处理。\n\n【建议】\n- 先恢复监测，再执行增氧和复测。',
            'reasoning': '',
            'usage': {'completion_tokens': 64},
            'finish_reason': 'stop',
            'answer_clean_meta': {'cleaned_length': 42},
            'reasoning_clean_meta': {'cleaned_length': 0},
            'truncated': False,
        }

        class FakeStreamResponse:
            status_code = 200
            headers = {'x-log-id': 'stream-unit-test'}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def iter_lines(self, decode_unicode=True):
                return iter([
                    'data: {"choices":[{"delta":{"content":"【结论】\\n"}}]}',
                    '',
                    'data: {"choices":[{"delta":{"content":"- 首轮流式答案被截断。"},"finish_reason":"length"}],"usage":{"completion_tokens":24}}',
                    '',
                    'data: [DONE]',
                    '',
                ])

        mock_post.return_value = FakeStreamResponse()

        state = {}
        events = list(_stream_bigmodel_events('unit-test-key', 'glm-5.1', '哪些断面需要优先处理？', {}, state))

        self.assertEqual(len(events), 3)
        self.assertIn('event: done', events[2])
        self.assertIn('黄竹尾水闸、杨洼闸、挖沟泵站需要优先处理', events[2])
        self.assertIn('"truncated": false', events[2])
        self.assertIn('"degraded": false', events[2])
        self.assertEqual(state['answer'], '【结论】\n- 黄竹尾水闸、杨洼闸、挖沟泵站需要优先处理。\n\n【建议】\n- 先恢复监测，再执行增氧和复测。')
        self.assertFalse(state['truncated'])


class DashboardAiEndpointTests(SimpleTestCase):
    def test_ai_insight_stream_request_has_json_fallback_for_content_negotiation(self):
        response = self.client.post(
            '/api/v1/dashboard/ai-insight/',
            data=json.dumps({'stream': True}),
            content_type='application/json',
            HTTP_ACCEPT='text/event-stream, application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'code': 400, 'message': '请提供问题或需求描述'},
        )

    @patch.dict(os.environ, {'SILICONFLOW_API_KEY': 'unit-test-key'}, clear=False)
    @patch('apps.dashboard.views._safe_create_ai_log')
    @patch('apps.dashboard.views._call_bigmodel')
    @patch('apps.dashboard.views._build_merged_ai_context')
    def test_ai_insight_returns_partial_answer_when_non_stream_result_is_truncated(
        self,
        mock_build_context,
        mock_call_bigmodel,
        _mock_create_ai_log,
    ):
        mock_build_context.return_value = ({'summary': {'total_devices': 1}}, 0.01)
        mock_call_bigmodel.return_value = {
            'answer': '【结论】\n- 保留已生成的部分回答。',
            'reasoning': '',
            'usage': {'completion_tokens': 24},
            'finish_reason': 'length',
            'attempts': 1,
            'token_budget': 640,
            'thinking_type': 'disabled',
            'log_id': 'unit-test-log',
            'context_stats': {'sensor_count': 10, 'sensor_limit': 10},
            'request_plan': {'max_tokens': 640},
            'answer_clean_meta': {'cleaned_length': 18},
            'reasoning_clean_meta': {'cleaned_length': 0},
            'truncated': True,
        }

        response = self.client.post(
            '/api/v1/dashboard/ai-insight/',
            data=json.dumps({
                'question': '哪些断面需要优先处理？',
                'context': {},
                'model': 'glm-5.1',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['answer'], '【结论】\n- 保留已生成的部分回答。')
        self.assertTrue(response.json()['data']['degraded'])
        self.assertTrue(response.json()['data']['truncated'])
