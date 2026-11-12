"""Publish a loopback review page for the current rebuild, without changing media."""

import html
import json
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "projects/悬崖上的小气球"
V = "正式前三段重制02"
batch_file = P / f"06-记录/视频生成/{V}-任务与结果.json"
batch = json.loads(batch_file.read_text(encoding="utf-8"))
items = []
for i, task in enumerate(batch["tasks"], 1):
    rel = Path(task["files"][0]).resolve().relative_to(P).as_posix()
    items.append((i, f"原生片段{i:02d}", rel))
items.append((4, "已剪辑·24帧·未通过试看", "04-输出/成片/正式前三段重制02-原速试看-24帧-未通过02.mp4"))
final = P / "04-输出/成片/正式前三段重制02-60帧-未通过试看-切镜保护.mp4"
if final.exists():
    items.append((5, "最终60帧·未通过试看", final.relative_to(P).as_posix()))
sections = "".join(
    f'<section><h2>{title}</h2><button onclick="play({i},0,null)">'
    f'从头1倍速播放{i}</button><video id="v{i}" controls preload="auto" '
    f'src="../../{html.escape(rel)}"></video><p id="s{i}"></p></section>'
    for i, title, rel in items
)
page = """<!doctype html><html lang="zh"><meta charset="utf-8">
<title>前三段重制·返回片检查</title><style>
body{background:#18212b;color:#eee;font:17px system-ui;margin:20px}
main{display:grid;grid-template-columns:1fr 1fr;gap:18px}video{width:100%}
h2{font-size:19px}button{font:inherit;padding:8px;margin:5px}</style>
<h1>正式前三段重制 · 未全部通过</h1>
<p>01额外浆果/未以龙躺姿开始；02短侧翻未执行；03女孩低位侧滚但中景被改成远景。
原始片保留，此页不代表用户整体接受。前两段首帧体高候选145/135px，参考145.3px；
姿态不同，不能据此证明3D体积恒定。</p>
<button onclick="play(4,7,11)">接口1·9秒切点前后原速</button>
<button onclick="play(4,13,17)">接口2·15秒切点前后原速</button>
__FINAL_BUTTONS__<main>__SECTIONS__</main><script>
let activeEnd=null;
function play(i,at,end){
 for(const v of document.querySelectorAll('video'))v.pause();
 let v=document.getElementById('v'+i);v.currentTime=at;v.playbackRate=1;
 activeEnd=end===null?null:{i,end};v.play();
}
function tick(){for(let i=1;i<=__COUNT__;i++){
 let v=document.getElementById('v'+i);
 document.getElementById('s'+i).textContent=
 `time=${v.currentTime.toFixed(3)}/${v.duration.toFixed(3)} rate=${v.playbackRate} ended=${v.ended}`;
 if(activeEnd&&activeEnd.i===i&&v.currentTime>=activeEnd.end){v.pause();activeEnd=null}
}requestAnimationFrame(tick)}tick();</script></html>"""
final_buttons = (
    '<button onclick="play(5,7,11)">60帧接口1原速复核</button>'
    '<button onclick="play(5,13,17)">60帧接口2原速复核</button>'
    if final.exists() else ""
)
page = page.replace("__SECTIONS__", sections).replace("__COUNT__", str(len(items)))
page = page.replace("__FINAL_BUTTONS__", final_buttons)
dest = P / f"05-检查与验收/{V}/返回视频与接缝复核.html"
dest.write_text(page, encoding="utf-8")
print(dest)
