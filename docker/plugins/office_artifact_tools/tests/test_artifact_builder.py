import unittest

from docx import Document
from pptx import Presentation

from tools.artifact_builder import build_docx_artifact, build_pptx_artifact, safe_filename


class ArtifactBuilderTests(unittest.TestCase):
    def test_safe_filename_adds_extension_and_removes_bad_chars(self):
        self.assertEqual(safe_filename('bad/name:*?', 'doc', '.docx'), 'bad_name_.docx')

    def test_build_docx_from_markdown(self):
        artifact = build_docx_artifact(
            title='MMB SaaS 方案',
            filename='mmb方案.docx',
            markdown_content='''# 结论\nMMB 应定位为设备运营系统。\n\n- 设备可靠性\n- 支付对账\n\n| 模块 | 价值 |\n| --- | --- |\n| 设备 | 在线监控 |\n''',
        )
        self.assertTrue(artifact.filename.endswith('.docx'))
        self.assertGreater(len(artifact.blob), 10000)
        self.assertEqual(artifact.summary['tables'], 1)
        import io

        doc = Document(io.BytesIO(artifact.blob))
        self.assertGreaterEqual(len(doc.paragraphs), 4)
        self.assertEqual(len(doc.tables), 1)

    def test_build_pptx_from_markdown_outline(self):
        artifact = build_pptx_artifact(
            title='MMB SaaS 方案',
            markdown_outline='''# 定位\n- 鲜啤设备运营系统\n- 支付和运维闭环\n\n# MVP\n- 设备可靠性\n- 订单对账\n''',
        )
        self.assertTrue(artifact.filename.endswith('.pptx'))
        self.assertGreater(len(artifact.blob), 10000)
        import io

        deck = Presentation(io.BytesIO(artifact.blob))
        self.assertEqual(len(deck.slides), 3)

    def test_empty_docx_content_is_rejected(self):
        with self.assertRaises(ValueError):
            build_docx_artifact(title='Empty', markdown_content='')

    def test_empty_ppt_content_is_rejected(self):
        with self.assertRaises(ValueError):
            build_pptx_artifact(title='Empty')


if __name__ == '__main__':
    unittest.main()
