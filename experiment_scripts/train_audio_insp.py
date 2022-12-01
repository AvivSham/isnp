# Enable import from parent package
import sys
import os

sys.path.append( os.path.dirname( os.path.dirname( os.path.abspath(__file__) ) ) )
import training_offline
import torch
import torch.nn as nn
import torch.nn.functional as F
# sys.path.append( os.path.dirname( os.path.dirname( os.path.abspath(__file__) ) ) )

import dataio, meta_modules, utils, loss_functions, modules

from torch.utils.data import DataLoader
import configargparse
from functools import partial

p = configargparse.ArgumentParser()
p.add('-c', '--config_filepath', required=False, is_config_file=True, help='Path to config file.')

p.add_argument('--logging_root', type=str, default='./logs', help='root for logging')
p.add_argument('--experiment_name', type=str, required=True,
               help='Name of subdirectory in logging_root where summaries and checkpoints will be saved.')

# General training options
p.add_argument('--batch_size', type=int, default=1)
p.add_argument('--noise_level', type=int, default=0)
p.add_argument('--lr', type=float, default=1e-3, help='learning rate. default=1e-4')
p.add_argument('--num_epochs', type=int, default=10000,
               help='Number of epochs to train for.')

p.add_argument('--epochs_til_ckpt', type=int, default=1000,
               help='Time interval in seconds until checkpoint is saved.')
p.add_argument('--steps_til_summary', type=int, default=100,
               help='Time interval in seconds until tensorboard summary is saved.')

p.add_argument('--model_type', type=str, default='sine',
               help='Options currently are "sine" (all sine activations), "relu" (all relu activations,'
                    '"nerf" (relu activations and positional encoding as in NeRF), "rbf" (input rbf layer, rest relu),'
                    'and in the future: "mixed" (first layer sine, other layers tanh)')
p.add_argument('--target', type=str, help='prediction type', default='sobel')
p.add_argument('--img_path', type=str, help='Path to Image.', default='div2k')
p.add_argument('--img_num', type=int, help='Path to Image.', default=1)
p.add_argument('--sz', type=int, help='Path to Image.', default=64)
p.add_argument('--sigma', type=float, help='Path to Image.', default=1)
p.add_argument('--overwrite', action='store_true')
p.add_argument('--checkpoint_path', default=None, help='Checkpoint to trained model.')
p.add_argument('--wav_path', type=str, default='data/gt_bach.wav', help='root for logging')

opt = p.parse_args()

audio_dataset = dataio.AudioFile(filename=opt.wav_path)
coord_dataset = dataio.AudioDenoise(audio_dataset)
image_resolution = (opt.sz, opt.sz)

dataloader = DataLoader(coord_dataset, shuffle=True, batch_size=opt.batch_size, pin_memory=False, num_workers=8)

class INSP(nn.Module):
    def __init__(self, in_c=3*23, out_c=3) -> None:
        super().__init__()
        self.fc1 = nn.Linear(in_c, 256)
        self.fc2 = nn.Linear(256, 256)
        self.fc3 = nn.Linear(256, 256)
        self.fc5 = nn.Linear(256, 256)
        self.fc4 = nn.Linear(256, out_c)
    def forward(self, data):
        x = data['grad']
        x = self.fc1(x)
        x = F.leaky_relu(x, negative_slope=0.2, inplace=True)
        x = self.fc2(x)
        x = F.leaky_relu(x, negative_slope=0.2, inplace=True)
        x = self.fc3(x)
        x = F.leaky_relu(x, negative_slope=0.2, inplace=True)
        x = self.fc5(x)
        x = F.leaky_relu(x, negative_slope=0.2, inplace=True)
        x = self.fc4(x)
        return {'new_img': x}

# Define the model.
model = INSP(in_c=8, out_c=1).cuda()
model.cuda()

root_path = os.path.join(opt.logging_root, opt.experiment_name)

# Define the loss
loss_fn = partial(loss_functions.color_mse_ray)
summary_fn = partial(utils.write_audio_summary, root_path)

training_offline.train(model=model, train_dataloader=dataloader, epochs=opt.num_epochs, lr=opt.lr,
               steps_til_summary=opt.steps_til_summary, epochs_til_checkpoint=opt.epochs_til_ckpt,
               model_dir=root_path, loss_fn=loss_fn, summary_fn=summary_fn, overwrite=opt.overwrite, clip_grad=False, sz=opt.sz)
