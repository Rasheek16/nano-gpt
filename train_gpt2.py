from dataclasses import dataclass
import torch
import torch.nn as nn
from torch.nn import functional as F
import math 


class CasualSelfAttention(nn.Module):
    def __init__(self,config):
        super().__init__()
        
        self.c_attn = nn.Linear(config.n_embd, 3*config.n_embd)
        
        self.c_proj = nn.Linear(config.n_embd , config.n_embd)
        
        self.n_head = config.n_head 
        self.n_embd = config.n_embd 
        
        self.register_buffer('bias',
                             torch.tril(torch.ones(config.block_size,config.block_size))
                             .view(1,1,config.block_size,config.block_size))
        
    def forward(self,x):
        
        B, T, C = x.size()
        
        qkv = self.c_attn(x)
        
        q, k ,v = qkv.split(self.n_embd , dim=2)
        
        k= k.view(B,T,self.n_head, C // self.n_head).transpose(1,2)
        q= q.view(B,T,self.n_head, C // self.n_head).transpose(1,2)
        v= v.view(B,T,self.n_head, C // self.n_head).transpose(1,2)
        
        att = (q@k.transpose(-2,-1)) * (1.0 / math.sqrt(k.siz(-1)))
        att = att.masked_fill(self.bias[:,:,:T,:T]==0,float('-inf'))
        att = F.softmax(att,dim = -1)
        y = att @ v 
        y = v.tranpose(1,2).contiguous().view(B,T,C)
        
        y = self.c_proj(y)
        
        return y 
        
    



class MLP(nn.Module):
    def __init__(self,config):
        super().__init__()
        self.c_fc   = nn.Linear(config.n_embd , 4* config.n_embd)
        self.gelu   = nn.GELU(approximate='tanh')
        self.c_proj = nn.Linear(4* config.n_embd,config)
    
    def forward(self,x):
        x = self.c_fc(x)
        x = self.gelu(x)
        x = self.c_proj(x)
        
        return x 
        
class Block(nn.Module):
    def __init__(self,config):
        super().__init__()
        self.ln_1 = nn.LayerNorm(config.n_embd)
        self.attn = CasualSelfAttention(config)
        self.ln_2 = nn.LayerNorm(config.n_embd)
        self.mlp = MLP(config)
        
    
    def forward(self,x):
        x = x + self.attn(self.ln_1(x))
        x = x + self.mlp(self.ln_2(x))
        
        return x
        
        


@dataclass
class GPTConfig:
    block_size: int = 1024
    vocab_size: int = 50257
    n_layers: int = 12
    n_head: int = 12
    n_embd: int = 768
    
class GPT(nn.Module):
    def __init__(self,config):
        super().__init__()
        self.config = config 
        
        self.transformer = nn.Module(dict(
            wte = nn.Embedding(config.vocab_size,config.n_embd),
            wpe = nn.Embedding(config.block_size,config.n_embd),
            h = nn.ModuleList([Block(config) for _ in range(config.n_layer)]),
            ln_f = nn.LayerNorm(config.n_embd),
        ))
        
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size , bias=False)
        
    
    @classmethod
    def from_pretrained(cls,model_type):
        assert model_type in  {'gpt2','gpt2-medium','gpt2-large','gpt2-xl'}
        
        from transformers import GPT2LMHeadModel
        print("Loading weights from pretrained gpt : %s" % model_type)
        
        
        config_args = {
            "gpt2"        : dict(n_layers = 12 , n_head =12 , n_emdd=768),
            "gpt2-medium" : dict(n_layers = 12 , n_head =12 , n_emdd= 1024),
            "gpt2-large"  : dict(n_layers = 12 , n_head =12 , n_emdd= 1024),
            "gpt2-xl"     : dict(n_layers = 12 , n_head =12 , n_emdd= 1024),
        }
        
        config = GPTConfig(**config_args)
        
        model  =GPT(config)
        
        sd = model.state_dict()
        
        sd_keys = sd.keys()
        
        sd_keys = [k for k in sd_keys if not k.endswith('.attn.bias')]
        
        model_hf = GPT2LMHeadModel.from_pretrained(model_type)
        
        sd_hf = model_hf.state_dict()
        
        
        