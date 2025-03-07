import onnx
import unittest
import torchvision
import numpy as np
from onnxruntime_customops.utils import trace_for_onnx, op_from_model
from onnxruntime_customops import eager_op, hook_model_op, PyOp, mytorch as torch


class TestTorchE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mobilenet = torchvision.models.mobilenet_v2(pretrained=True)
        cls.argmax_input = None

    @staticmethod
    def on_hook(*x):
        TestTorchE2E.argmax_input = x[0]
        return x

    def test_imagenet_postprocess(self):
        mb_core_path = "mobilev2.onnx"
        mb_full_path = "mobilev2_full.onnx"
        dummy_input = torch.randn(10, 3, 224, 224)
        np_input = dummy_input.numpy()
        torch.onnx.export(self.mobilenet, dummy_input, mb_core_path, opset_version=11)
        mbnet2 = op_from_model(mb_core_path)

        with trace_for_onnx(dummy_input, names=['b10_input']) as tc_sess:
            scores = mbnet2(*tc_sess.get_inputs())
            probabilities = torch.softmax(scores, dim=1)
            batch_top1 = probabilities.argmax(dim=1)

            np_argmax = probabilities.numpy()  # for the result comparison
            np_output = batch_top1.numpy()

            tc_sess.save_as_onnx(mb_full_path, batch_top1)

        hkdmdl = hook_model_op(onnx.load_model(mb_full_path), 'argmax', self.on_hook, [PyOp.dt_float])
        mbnet2_full = eager_op.EagerOp.from_model(hkdmdl)
        batch_top1_2 = mbnet2_full(np_input)
        np.testing.assert_allclose(np_argmax, self.argmax_input, rtol=1e-5)
        np.testing.assert_array_equal(batch_top1_2, np_output)


if __name__ == "__main__":
    unittest.main()
