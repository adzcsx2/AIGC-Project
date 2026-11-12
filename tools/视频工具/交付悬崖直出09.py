"""Validate the single full-timeline RIFE result and export five review units."""
from pathlib import Path
import argparse,json,subprocess,hashlib,importlib.util
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'projects/悬崖上的小气球'
TAG='正式五段直出09'
spec=importlib.util.spec_from_file_location('r09_helpers',Path(__file__).with_name('检查合成悬崖直出09.py'))
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
read,save,probe,run,sha=helpers.read,helpers.save,helpers.probe,helpers.run,helpers.sha

def main(final):
 rec=read(helpers.REC);pack=read(helpers.PACK);native=P/rec['combined']['path'];assert sha(native)==rec['combined']['sha256']
 final=Path(final).resolve(strict=True);assert final.is_relative_to(P.resolve());info=probe(final);v=next(s for s in info['streams'] if s['codec_type']=='video')
 expected=sum(u['used_range'][1]-u['used_range'][0] for u in rec['units']);assert v['avg_frame_rate']=='60/1' and int(v['nb_frames'])==round(expected*60)
 run(['ffmpeg','-v','error','-i',final,'-f','null','-'])
 output=P/'04-输出/独立片段'/TAG;output.mkdir(parents=True,exist_ok=True);items=[]
 for u in sorted(rec['units'],key=lambda x:x['n']):
  unit=next(x for x in pack['units'] if x['n']==u['n']);start,end=u['timeline'];f=output/f"片段{u['n']:02d}-{unit['name']}-60帧待审01.mp4"
  if not f.exists():
   run(['ffmpeg','-v','error','-n','-i',final,'-filter_complex',f'[0:v:0]trim=start_frame={round(start*60)}:end_frame={round(end*60)},setpts=PTS-STARTPTS[v];[0:a:0]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a]',
        '-map','[v]','-map','[a]','-c:v','libx264','-crf','16','-preset','fast','-c:a','aac','-b:a','192k','-movflags','+faststart',f])
  q=probe(f);vs=next(x for x in q['streams'] if x['codec_type']=='video');assert int(vs['nb_frames'])==round((end-start)*60)
  run(['ffmpeg','-v','error','-i',f,'-f','null','-'])
  items.append(dict(n=u['n'],path=f.relative_to(P).as_posix(),sha256=sha(f),native_source=u['source'],timeline=[start,end],fps=60,frames=int(vs['nb_frames']),full_decode='PASS',quality=u.get('actual_visual_review',{})))
  print(json.dumps(dict(n=u['n'],exported=str(f.relative_to(P)),frames=vs['nb_frames']),ensure_ascii=False),flush=True)
 dest=P/f'06-记录/后期制作/{TAG}-最终预览交付02.json'
 save(dest,dict(native=rec['combined'],preview_60fps=dict(path=final.relative_to(P.resolve()).as_posix(),sha256=sha(final),probe=info,full_decode='PASS'),units=items,
               quality_status='NOT_PASSED',user_acceptance=None,role_layer_composite=False,subject_scaling_or_local_warp=False,retiming=False,
               note='Single u30 source per unit, one full-timeline RIFE pass after edit/merge. Independent files are exact timeline selections from that preview, re-encoded without another interpolation. Body/time failures retained and labeled, not repaired by frame-rate conversion.'))
 print('Preview delivery record:',dest,flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('final');main(ap.parse_args().final)
