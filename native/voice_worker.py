"""Local Supertonic 3 voices (F1-F5 female, M1-M5 male). stdin JSON -> output WAV. No network.
Exit code 3 = the requested voice style file is not installed (the app then falls back to a macOS voice)."""
import json,re,sys
from pathlib import Path
base=Path(__file__).resolve().parent
value=json.load(sys.stdin)
voice=str(value.get('voice') or '')
if not re.fullmatch(r'[FM][1-5]',voice):voice='F1' if value.get('style')=='calm' else 'F3'
style_file=base/'voice_styles'/(voice+'.json')
if not style_file.exists():sys.exit(3)
sys.path.insert(0,str(base/'packages'))
from helper import ort,load_cfgs,load_onnx_all,load_text_processor,TextToSpeech,load_voice_style
import soundfile as sf
opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
models=str(base/'onnx')
tts=TextToSpeech(load_cfgs(models),load_text_processor(models),*load_onnx_all(models,opts,['CPUExecutionProvider']))
style=load_voice_style([str(style_file)])
text=str(value['text'])[:1200]
# Brisk but clear: base 1.28 (1.18 felt slow). Deep voices sound rushed when sped up equally, so they get a small trim.
speed=1.28*{'M3':0.95,'M4':0.97,'F3':0.98}.get(voice,1.0)
steps=8  # 5 is the low-quality floor; 8 is the upstream default and sounds noticeably smoother
wav,duration=tts(text,'tr' if value.get('lang')=='tr' else 'en',style,steps,speed)
sf.write(value['output'],wav[0,:int(tts.sample_rate*duration[0].item())],tts.sample_rate)
