import os
import json

import torch
import numpy as np

from model import FastSpeech2, GaussianDiffusion, ScheduledOptim

from hfgan.vocoder import Vocoder


def get_model(args, configs, device, train=False):
    (preprocess_config, model_config, train_config) = configs

    ModelCls = GaussianDiffusion if "model_cls" in model_config and \
                                    model_config["model_cls"]=="GaussianDiffusion" else FastSpeech2

    model = ModelCls(preprocess_config, model_config).to(device)
    if args.restore_step:
        ckpt_path = os.path.join(
            train_config["path"]["ckpt_path"],
            "{}.pth.tar".format(args.restore_step),
        )
        ckpt = torch.load(ckpt_path)
        model.load_state_dict(ckpt["model"])

    if train:
        scheduled_optim = ScheduledOptim(
            model, train_config, model_config, args.restore_step
        )
        if args.restore_step:
            scheduled_optim.load_state_dict(ckpt["optimizer"])
        model.train()
        return model, scheduled_optim

    model.eval()
    model.requires_grad_ = False
    return model


def get_param_num(model):
    num_param = sum(param.numel() for param in model.parameters())
    return num_param


def get_vocoder(config, device):
    name = config["vocoder"]["model"]
    speaker = config["vocoder"]["speaker"]

    if name == "MelGAN":
        if speaker == "LJSpeech":
            vocoder = torch.hub.load(
                "descriptinc/melgan-neurips", "load_melgan", "linda_johnson"
            )
        elif speaker == "universal":
            vocoder = torch.hub.load(
                "descriptinc/melgan-neurips", "load_melgan", "multi_speaker"
            )
        vocoder.mel2wav.eval()
        vocoder.mel2wav.to(device)
    elif name =="hifigan":
        ckpt_path = config["vocoder"]["ckpt"]
        vocoder = Vocoder(ckpt_path, device=device)

    return vocoder


def vocoder_infer(mels, vocoder, model_config, preprocess_config, lengths=None):
    name = model_config["vocoder"]["model"]
    with torch.no_grad():
        if name == "MelGAN":
            wavs = vocoder.inverse(mels / np.log(10))
        elif name == "hifigan":
            wavs = [vocoder.mel2wav(mel) for mel in mels]

    # wavs = (
    #     wavs.cpu().numpy()
    #     * preprocess_config["preprocessing"]["audio"]["max_wav_value"]
    # ).astype("int16")
    # wavs = [wav for wav in wavs]

    for i in range(len(mels)):
        if lengths is not None:
            wavs[i] = wavs[i][: lengths[i]]

    return wavs
