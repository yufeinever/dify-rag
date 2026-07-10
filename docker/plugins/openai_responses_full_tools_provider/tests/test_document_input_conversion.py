import unittest

from dify_plugin.entities.model.message import (
    DocumentPromptMessageContent,
    ImagePromptMessageContent,
    TextPromptMessageContent,
    UserPromptMessage,
)

from models.llm.llm import OpenAILargeLanguageModel


class DocumentInputConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = object.__new__(OpenAILargeLanguageModel)

    def convert_user_content(self, content: list) -> list[dict]:
        converted = self.model._convert_prompt_messages_to_responses_input(
            [UserPromptMessage(content=content)]
        )
        self.assertEqual(len(converted), 1)
        return converted[0]["content"]

    def test_converts_document_url_to_input_file(self) -> None:
        document = DocumentPromptMessageContent(
            format="docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="方案.docx",
            url="https://files.example.test/plan.docx",
        )

        content = self.convert_user_content([document])

        self.assertEqual(
            content,
            [
                {
                    "type": "input_file",
                    "filename": "方案.docx",
                    "file_url": "https://files.example.test/plan.docx",
                }
            ],
        )

    def test_converts_base64_document_to_input_file(self) -> None:
        document = DocumentPromptMessageContent(
            format="pdf",
            mime_type="application/pdf",
            filename="report.pdf",
            base64_data="JVBERi0xLjQ=",
        )

        content = self.convert_user_content([document])

        self.assertEqual(
            content,
            [
                {
                    "type": "input_file",
                    "filename": "report.pdf",
                    "file_data": "data:application/pdf;base64,JVBERi0xLjQ=",
                }
            ],
        )

    def test_uses_generated_filename_when_document_name_is_missing(self) -> None:
        document = DocumentPromptMessageContent(
            format="txt",
            mime_type="text/plain",
            base64_data="aGVsbG8=",
        )

        content = self.convert_user_content([document])

        self.assertEqual(content[0]["filename"], "attachment.txt")

    def test_rejects_document_without_data_or_url(self) -> None:
        document = DocumentPromptMessageContent(
            format="docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="empty.docx",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Document attachment has no base64 data or URL: empty.docx",
        ):
            self.convert_user_content([document])

    def test_text_and_image_conversion_remain_unchanged(self) -> None:
        text = TextPromptMessageContent(data="hello")
        image = ImagePromptMessageContent(
            format="png",
            mime_type="image/png",
            filename="preview.png",
            base64_data="aW1hZ2U=",
        )

        content = self.convert_user_content([text, image])
