import os

import torch

from models import (
    MICN,
    Autoformer,
    Crossformer,
    DLinear,
    ETSformer,
    FEDformer,
    FiLM,
    FreTS,
    Informer,
    Koopa,
    LightTS,
    MambaSimple,
    Nonstationary_Transformer,
    PatchTST,
    PAttn,
    Pyraformer,
    Reformer,
    SCINet,
    SegRNN,
    TemporalFusionTransformer,
    TiDE,
    TimeMixer,
    TimesNet,
    Transformer,
    TSMixer,
    iTransformer,
)


class Exp_Basic(object):
    def __init__(self, args):
        self.args = args
        self.model_dict = {
            "TimesNet": TimesNet,
            "Autoformer": Autoformer,
            "Transformer": Transformer,
            "Nonstationary_Transformer": Nonstationary_Transformer,
            "DLinear": DLinear,
            "FEDformer": FEDformer,
            "Informer": Informer,
            "LightTS": LightTS,
            "Reformer": Reformer,
            "ETSformer": ETSformer,
            "PatchTST": PatchTST,
            "Pyraformer": Pyraformer,
            "MICN": MICN,
            "Crossformer": Crossformer,
            "FiLM": FiLM,
            "iTransformer": iTransformer,
            "Koopa": Koopa,
            "TiDE": TiDE,
            "FreTS": FreTS,
            "MambaSimple": MambaSimple,
            "TimeMixer": TimeMixer,
            "TSMixer": TSMixer,
            "SegRNN": SegRNN,
            "TemporalFusionTransformer": TemporalFusionTransformer,
            "SCINet": SCINet,
            "PAttn": PAttn,
        }
        if args.model == "Mamba":
            print("Please make sure you have successfully installed mamba_ssm")
            from models import Mamba

            self.model_dict["Mamba"] = Mamba

        self.device = self._acquire_device()
        self.model = self._build_model().to(self.device)

    def _build_model(self):
        raise NotImplementedError
        return None

    def _acquire_device(self):
        if self.args.use_gpu:
            os.environ["CUDA_VISIBLE_DEVICES"] = (
                str(self.args.gpu) if not self.args.use_multi_gpu else self.args.devices
            )
            device = torch.device("cuda:{}".format(self.args.gpu))
            print("Use GPU: cuda:{}".format(self.args.gpu))
        else:
            device = torch.device("cpu")
            print("Use CPU")
        return device

    def _get_data(self):
        pass

    def vali(self):
        pass

    def train(self):
        pass

    def test(self):
        pass
