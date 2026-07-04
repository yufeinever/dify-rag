from types import SimpleNamespace
import unittest

from models.llm.responses_tool_parser import (
    append_function_call_arguments_delta,
    collect_response_output_function_calls,
    finalize_function_call_arguments,
    item_to_function_call_data,
    merge_function_call_data,
    normalize_function_name,
    valid_function_call_data,
)


class ResponsesToolParserTests(unittest.TestCase):
    def test_output_item_done_restores_function_name(self):
        pending = {}
        added = SimpleNamespace(type="function_call", call_id="call_1", name="", arguments="")
        done = SimpleNamespace(type="function_call", call_id="call_1", name="search_segments", arguments='{"query":"MMB"}')

        merge_function_call_data(pending, 0, item_to_function_call_data(added, "call_1"))
        finalize_function_call_arguments(pending, 0, '{"query":"MMB"}', "", "call_1")
        merge_function_call_data(pending, 0, item_to_function_call_data(done, "call_1"))

        calls = valid_function_call_data(pending.values(), {"search_segments"})
        self.assertEqual(calls, [{"call_id": "call_1", "name": "search_segments", "arguments": '{"query":"MMB"}'}])

    def test_blank_or_hosted_tool_items_do_not_become_dify_tool_calls(self):
        output = [
            SimpleNamespace(type="web_search_call", id="ws_1"),
            SimpleNamespace(type="function_call", call_id="call_2", name="", arguments="{}"),
            SimpleNamespace(type="function_call", call_id="call_3", name="unknown_tool", arguments="{}"),
        ]

        pending = collect_response_output_function_calls(output)
        self.assertEqual(valid_function_call_data(pending.values(), {"search_segments"}), [])

    def test_argument_delta_can_arrive_before_added_item(self):
        pending = {}
        append_function_call_arguments_delta(pending, 0, '{"query"', "call_4")
        append_function_call_arguments_delta(pending, 0, ':"MMB"}', "call_4")
        finalize_function_call_arguments(pending, 0, '{"query":"MMB"}', "search_segments", "call_4")

        calls = valid_function_call_data(pending.values(), {"search_segments"})
        self.assertEqual(calls[0]["name"], "search_segments")
        self.assertEqual(calls[0]["arguments"], '{"query":"MMB"}')


    def test_dict_function_call_item_restores_name(self):
        output = [
            {
                "type": "function_call",
                "call_id": "call_5",
                "name": "generate_word_document",
                "arguments": '{"title":"方案","markdown_content":"# 方案"}',
            }
        ]

        pending = collect_response_output_function_calls(output)
        calls = valid_function_call_data(pending.values(), {"generate_word_document"})

        self.assertEqual(calls[0]["call_id"], "call_5")
        self.assertEqual(calls[0]["name"], "generate_word_document")
        self.assertEqual(calls[0]["arguments"], '{"title":"方案","markdown_content":"# 方案"}')

    def test_blank_allowed_names_are_ignored(self):
        calls = valid_function_call_data([{"call_id": "call_6", "name": "", "arguments": "{}"}], {""})
        self.assertEqual(calls, [])


    def test_blank_name_can_infer_word_tool_from_arguments(self):
        calls = valid_function_call_data(
            [
                {
                    "call_id": "call_7",
                    "name": "",
                    "arguments": '{"filename":"方案.docx","markdown_content":"# 方案"}',
                }
            ],
            {"generate_word_document", "search_segments"},
        )

        self.assertEqual(calls[0]["name"], "generate_word_document")

    def test_blank_name_can_infer_search_segments_from_arguments(self):
        calls = valid_function_call_data(
            [
                {
                    "call_id": "call_8",
                    "name": "",
                    "arguments": '{"query":"MMB 创始人","limit":5}',
                }
            ],
            {"generate_word_document", "search_segments"},
        )

        self.assertEqual(calls[0]["name"], "search_segments")



    def test_blank_name_can_infer_excel_tool_from_arguments(self):
        calls = valid_function_call_data(
            [
                {
                    "call_id": "call_excel",
                    "name": "",
                    "arguments": '{"filename":"预算.xlsx","title":"预算","content":"# 预算\\n\\n| 项目 | 金额 |"}',
                }
            ],
            {"generate_excel_workbook", "generate_word_document"},
        )

        self.assertEqual(calls[0]["name"], "generate_excel_workbook")

    def test_blank_name_prefers_unified_office_tool_from_artifact_type(self):
        calls = valid_function_call_data(
            [
                {
                    "call_id": "call_office",
                    "name": "",
                    "arguments": '{"artifact_type":"excel","title":"预算","content":"# 预算"}',
                }
            ],
            {"create_office_artifact", "generate_excel_workbook", "generate_word_document"},
        )

        self.assertEqual(calls[0]["name"], "create_office_artifact")

    def test_functions_prefix_is_stripped(self):
        calls = valid_function_call_data(
            [
                {
                    "call_id": "call_9",
                    "name": "functions.generate_word_document",
                    "arguments": '{"filename":"方案.docx","markdown_content":"# 方案"}',
                }
            ],
            {"generate_word_document"},
        )

        self.assertEqual(calls[0]["name"], "generate_word_document")

    def test_chat_tool_name_normalizer_infers_blank_name(self):
        name = normalize_function_name("", '{"filename":"方案.docx","markdown_content":"# 方案"}')
        self.assertEqual(name, "generate_word_document")

    def test_chat_tool_name_normalizer_infers_blank_excel_name(self):
        name = normalize_function_name("", '{"filename":"预算.xlsx","content":"# 预算"}')
        self.assertEqual(name, "generate_excel_workbook")


if __name__ == "__main__":
    unittest.main()
