# Copyright 2020 Tencent
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import sys
import torch
import turbo_transformers
from transformers import BertTokenizer
from transformers.modeling_bert import BertConfig, BertPooler
import numpy
import os

sys.path.append(os.path.dirname(__file__))
import test_helper


def create_test(batch_size, seq_length):
    class TestBertPooler(unittest.TestCase):
        def init_data(self, use_cuda: bool) -> None:
            # we do not support GPU pooler for now
            if use_cuda:
                return
            self.test_device = torch.device('cpu:0')
            torch.set_num_threads(1)

            torch.set_grad_enabled(False)
            self.tokenizer = BertTokenizer.from_pretrained(
                os.path.join(os.path.dirname(__file__), 'test-model'))
            self.cfg = BertConfig(
                vocab_size_or_config_json_file=self.tokenizer.vocab_size)

            self.torch_pooler = BertPooler(self.cfg)
            if torch.cuda.is_available():
                self.torch_pooler.to(self.test_device)
            self.torch_pooler.eval()

            self.turbo_pooler = turbo_transformers.BertPooler.from_torch(
                self.torch_pooler)

        def check_torch_and_turbo(self, use_cuda):
            if use_cuda:
                return
            self.init_data(use_cuda=use_cuda)
            device = "CPU"
            num_iter = 2
            hidden_size = self.cfg.hidden_size
            input_tensor = torch.rand(size=(batch_size, seq_length,
                                            hidden_size),
                                      dtype=torch.float32,
                                      device=self.test_device)
            turbo_model = lambda: self.turbo_pooler(input_tensor)
            turbo_result, turbo_qps, turbo_time = \
                test_helper.run_model(turbo_model, use_cuda, num_iter)

            print(
                f"BertPooler \"({batch_size},{seq_length:03})\" ",
                f"{device} TurboTransform QPS,  {turbo_qps}, time, {turbo_time}"
            )

            torch_model = lambda: self.torch_pooler(input_tensor)
            torch_result, torch_qps, torch_time = \
                test_helper.run_model(torch_model, use_cuda, num_iter)
            print(f"BertPooler \"({batch_size},{seq_length:03})\" ",
                  f"{device} Torch QPS,  {torch_qps}, time, {torch_time}")

            torch_result = torch_result.cpu().numpy()
            turbo_result = turbo_result.cpu().numpy()

            self.assertTrue(
                numpy.allclose(torch_result,
                               turbo_result,
                               rtol=1e-4,
                               atol=1e-3))

            with open("bert_pooler_res.txt", "a") as fh:
                fh.write(
                    f"\"({batch_size},{seq_length:03})\", {torch_qps}, {torch_qps}\n"
                )

        def test_pooler(self):
            self.check_torch_and_turbo(use_cuda=False)

    globals()[f"TestBertPooler_{batch_size}_{seq_length:03}"] = \
        TestBertPooler


with open("bert_pooler_res.txt", "w") as fh:
    fh.write(", torch, turbo_transformers\n")
    for batch_size in [1, 2, 4, 8, 50, 100]:
        for seq_length in [1]:
            create_test(batch_size, seq_length)

if __name__ == '__main__':
    unittest.main()