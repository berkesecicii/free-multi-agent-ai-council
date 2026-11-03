"""Local Supertonic 3 F3/F1 female voice. stdin JSON -> output WAV. No network."""
import json,sys
from pathlib import Path
base=Path(__file__).resolve().parent
sys.path.insert(0,str(base/'packages'))
from helper import ort,load_cfgs,load_onnx_all,load_text_processor,TextToSpeech,load_voice_style
import soundfile as sf
value=json.load(sys.stdin)
opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
models=str(base/'onnx')
tts=TextToSpeech(load_cfgs(models),load_text_processor(models),*load_onnx_all(models,opts,['CPUExecutionProvider']))
profile='F1' if value.get('style')=='calm' else 'F3'
style=load_voice_style([str(base/'voice_styles'/(profile+'.json'))])
text=str(value['text'])[:1200]
wav,duration=tts(text,'tr' if value.get('lang')=='tr' else 'en',style,5,1.18)  # speed: 0.97 was too slow; 1.18 is brisk but clear
sf.write(value['output'],wav[0,:int(tts.sample_rate*duration[0].item())],tts.sample_rate)
