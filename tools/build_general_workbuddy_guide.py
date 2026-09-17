from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf/general-pixel-art-to-3mf-workbuddy-guide.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
(ROOT/'output/packages').mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('CJK','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
NAVY=colors.HexColor('#163442'); TEAL=colors.HexColor('#167D83'); PALE=colors.HexColor('#EDF5F4'); GRAY=colors.HexColor('#576B73'); LINE=colors.HexColor('#D3E0E2')
W,H=A4; CW=W-88
styles={
 'title':ParagraphStyle('title',fontName='CJK',fontSize=27,leading=36,textColor=NAVY,spaceAfter=14,wordWrap='CJK'),
 'h':ParagraphStyle('h',fontName='CJK',fontSize=21,leading=29,textColor=NAVY,spaceAfter=13,wordWrap='CJK'),
 'sub':ParagraphStyle('sub',fontName='CJK',fontSize=12.5,leading=19,textColor=TEAL,spaceBefore=10,spaceAfter=7,wordWrap='CJK'),
 'body':ParagraphStyle('body',fontName='CJK',fontSize=10,leading=16,textColor=NAVY,spaceAfter=8,wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='CJK',fontSize=8.5,leading=13,textColor=GRAY,spaceAfter=5,wordWrap='CJK'),
 'code':ParagraphStyle('code',fontName='CJK',fontSize=9,leading=14,textColor=NAVY,spaceAfter=0,wordWrap='CJK'),
 'tag':ParagraphStyle('tag',fontName='CJK',fontSize=8.5,leading=14,textColor=TEAL,spaceAfter=9),
}
story=[]
def p(t,k='body'):return Paragraph(t,styles[k])
def add(t,k='body'):story.append(p(t,k))
def start(n,title,subtitle):
 if story:story.append(PageBreak())
 add(f'PIXEL3MF / WORKBUDDY     GUIDE {n:02d}', 'tag')
 add(title,'title' if n==1 else 'h');add(subtitle)
def box(text):
 tab=Table([[p(escape(text).replace('\n','<br/>'),'code')]],colWidths=[CW])
 tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.5,LINE),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
 story.extend([tab,Spacer(1,10)])
def table(rows,widths):
 data=[[p(escape(str(v)), 'body' if i==0 else 'small') for v in row] for i,row in enumerate(rows)]
 t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),PALE),('LINEBELOW',(0,0),(-1,0),.8,TEAL),('LINEBELOW',(0,1),(-1,-1),.3,LINE),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
 story.extend([t,Spacer(1,8)])
def foot(c,doc):
 c.setStrokeColor(LINE);c.line(44,42,W-44,42)
 c.setFont('CJK',8);c.setFillColor(GRAY)
 c.drawString(44,28,'通用像素画转 3MF · WorkBuddy · 2026-09-17')
 c.drawRightString(W-44,28,f'{doc.page} / 5')

start(1,'通用像素画转 3MF','WorkBuddy 使用说明 · 先 Perfect Pixel，后正式验收')
add('适用于人物、宠物、植物、物品、车辆、建筑和简洁场景。输入可以是文字、参考图或实拍照片。')
ref=ROOT/'skills/codex/general-pixel-art-to-3mf/assets/reference-corgi-pixel-style.png'
img=Image(str(ref),width=145,height=145*28/26,mask='auto')
t=Table([[img,p('默认风格参考：已处理的柯基<br/><br/>逻辑网格 26 × 28，透明度为 0/255。参考其规整色块、阶梯轮廓和简化程度；生成其他主体时，不复制柯基的外形、毛色或坐姿。','body')]],colWidths=[178,CW-178])
t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BACKGROUND',(0,0),(0,0),colors.HexColor('#DDE5E7')),('LEFTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12)]))
story.extend([Spacer(1,4),t,Spacer(1,14)])
add('先确认安装与工作空间','sub')
add('打开 WorkBuddy，并选择已部署的 Pixel3MF 项目。若换电脑或重新导入，在技能管理中导入配套 ZIP，并启用 general-pixel-art-to-3mf；具体入口名称以当前界面为准。')
box('当前解压并部署的 Pixel3MF 项目目录')
add('配套文件：general-pixel-art-to-3mf-workbuddy.zip','small')
add('项目级入口：.codebuddy/skills/general-pixel-art-to-3mf/SKILL.md。使用同一份最新版，避免误选原来的动漫专用 pixel-art-to-3mf。','small')
add('运行前提','sub')
add('需要已经部署的 Pixel3MF 项目、.venv、Lumina-Layers 和相关依赖。ZIP 内含流程说明、柯基参考图和新版像素整理脚本；不包含完整软件、模型权重或账户凭据。')
add('验证范围：已在 WorkBuddy 内用 DeepSeek Flash 调度、原生 ImageGen 生图，完成一次纯白底柯基到两份 3MF 的真实流程。只生成 1 张，无生图重试；通过背景复核保住白毛。尚未实物打印。','small')

start(2,'复制一段指令即可开始','优先直接说明主体、要保留的特征，以及最终要 PNG 还是 3MF。')
add('从文字生成，并完成两份 3MF','sub')
box('请使用 general-pixel-art-to-3mf 通用 Skill，生成一只完整坐姿、略侧身的棕白柯基，保留大耳朵、短腿和白胸毛，并完成两份 3MF。\n使用当前 Skill 的短提示词和内置柯基风格参考；统一生成纯白、不透明背景，之后由程序移除背景。原图只做轻量预检，先经过 Perfect Pixel 整理，再正式验收。\n验收通过后继续生成 Lumina 预览及 2×2、3×3 两种成品，不要停在生图阶段。保留源图、中间文件和 manifest。生图最多 3 次，合格后停止重试。')
add('使用照片或多张参考图','sub')
box('请使用 general-pixel-art-to-3mf，将我附的宠物照片转成粗像素画。第一张负责主体外观和花纹；第二张只参考坐姿。内置柯基图只参考像素块风格，不要把我的宠物画成柯基。\n保留耳朵轮廓、眼睛颜色和胸前花纹，使用纯白、不透明背景。先处理背景和整理像素，再验收，再导出两份 3MF。')
add('将图片作为附件，或提供 WorkBuddy 能读取的本地路径，并说明每张图片的用途。执行时需要通过图像工具的实际参考图参数附图，仅在提示词中写路径不等于传入图片。','small')
add('只要 PNG / 直接转换现有像素图','sub')
box('只要成品 PNG：请使用通用 Skill 画一盆仙人掌，经过 Perfect Pixel 整理和正式验收后，交付逻辑像素 PNG 与放大预览，不转换 3MF。\n\n现成像素图：请使用通用 Skill 直接转换附件像素图，保留原图，不重新生图；完成必要整理、验收和两份 3MF。')
add('“参考照片生成像素画”会重绘。若想原照片直接转换，并保留连续色调和细节，应使用高保真工作流，而不是通用像素版。','small')

start(3,'一次任务如何执行','先让 Perfect Pixel 处理可恢复的问题，再判断像素成品是否可用。')
table([['阶段','执行内容与检查重点'],['1  输入与生图','确认照片/风格/构图参考的分工；生成粗像素源图。固定纯白、不透明背景，不要求工具生成透明图。记录实际图像模型，而非调度模型。'],['2  原图轻量预检','只拦截文件不可读、主体错误、重要部位缺失或被裁掉等问题。渐变、抗锯齿、半透明边缘和颜色偏多先记录，继续整理。'],['3  Perfect Pixel','自动检测网格并采样。先对纯白源图做必要的背景分割；采样后将逻辑格 Alpha 二值化，再紧裁外部透明行列。'],['4  正式验收','对照原图检查主体、关键花纹、轮廓、白色细节和透明孔洞。看逻辑图与最近邻放大预览，不只看原始生图。'],['5  Lumina 预览','按最终网格和当前 LUT 生成叠色预览，检查颜色变化、主体缺失、背景残留。'],['6  导出与交付','分别导出 2×2、3×3 两份 3MF，保留 ZIP、预览、参数和验收记录。最终文件包含流程约定的后处理。']],[105,CW-105])
add('怎样判断“够好”，而不是过度审查','sub')
add('以整理后的主体可辨认、网格可读、轮廓完整、背景正确为准。颜色超过提示词中的 6–8 色、网格不是 24×24、不同格之间存在少量阶梯色阶，都不是单独的拒绝理由。')
add('通用版不套用动漫版的“源图每轴 60–85 格”门槛，也不强行缩成 24×24。Perfect Pixel 自动检测失败、整理后主体残缺或遮罩仍有歧义，才需要针对性修正。')
add('白底生图，后处理移除背景','sub')
add('WorkBuddy 生图固定使用纯白、不透明背景，不发送透明背景参数。后处理通过分割或遮罩生成打印所需的透明区域，保留白毛、眼白等前景。最终 Alpha 二值化发生在逻辑格采样后。')

start(4,'输出文件与模型尺寸','每次运行新建 output/时间戳_主体名/，源图与中间文件都保留。')
table([['文件','用途'],['00_subject_brief.md','记录需求、参考图分工、需要保留的特征与背景选择。'],['01_source.png','未覆盖的源图；生成工具原始文件也应保留。'],['03_working_grid.png','Perfect Pixel 整理后的工作网格。'],['04_pixel_perfect.png','最终紧裁逻辑网格；是物理尺寸的唯一依据。'],['05_pixel_preview_8x.png','8 倍最近邻预览，检查轮廓、颜色与透明孔洞。'],['06_lumina_2d_preview_*.png','两种映射密度的 Lumina 叠色预览。'],['07_lumina_batch_result_*.zip','原始 Lumina 归档；不当作完成后处理的最终模型。'],['08_*_2x2.3mf / 08_*_3x3.3mf','两份最终交付模型。'],['manifest.json','来源、参数、实际网格、尺寸、处理记录与验收状态。']],[230,CW-230])
add('两种尺寸如何计算','sub')
table([['本次实测最终 17×21 网格','2×2 版本','3×3 版本'],['最终逻辑像素间距','0.84 mm','1.29 mm'],['名义宽 × 高','14.28 × 17.64 mm','21.93 × 27.09 mm']],[225,(CW-225)/2,(CW-225)/2])
add('上表为本次 WorkBuddy 实测的名义画布尺寸，不是固定打印尺寸；网格边缘间隙使实际几何外包尺寸略小。3×3 先按 1.26 mm 间距生成，再由程序将 XY 乘以 43/42；Z 不变。不要在切片器里重复放大。','small')
add('导出默认值','sub')
add('背板 1.2 mm、双面结构、不加挂孔，使用 BambuLab PLA 红/蓝/黄/白 LUT。最终 3MF 使用项目约定的 A1 mini 0.4 mm 机器与 0.08 mm 工艺配置；切片前仍需核对实际设备、耗材映射和尺寸。')

start(5,'常见问题与维护','先定位发生在哪个阶段，再做最小修正，避免无效重复生图。')
table([['遇到的问题','应如何处理'],['仍套用动漫上半身规则，或在 60–85 格处拒绝','明确选择 general-pixel-art-to-3mf；加载项目级新版本，不调用旧动漫候选验收/转换入口。'],['找不到 --png-only 或 --binarize-alpha','使用 Skill 自带 scripts/refine_pixel.py，而不是旧项目同名脚本；配合项目 .venv/bin/python。'],['No module named PIL / perfect_pixel','确认正在使用已有项目 .venv。不要因为系统 Python 缺包就重复安装整套环境。'],['图片有渐变或半透明边缘','先经过 Perfect Pixel，再检查逻辑图。不要只因原图有这些现象反复重画。'],['棋盘格被保留、白毛丢失、孔洞填实','先复核白毛与背景。封闭描边、无歧义孔洞的简单白底图，可用仅移除外连通白色的方案；其他情况复核语义遮罩。'],['自动网格检测失败','保留源图与诊断，尝试更清晰的新源图；不要强制网格或缩图制造通过。'],['生成任务状态未知或暂时失败','先查已提交调用状态，避免重复付费；不自动切换图像服务。'],['有 PNG，没有 3MF','确认最初要求了完整导出，再查正式验收、Lumina 预览和转换错误；不能仅凭脚本返回成功代替图像验收。']],[166,CW-166])
add('维护者：更新与打包','sub')
add('在同一项目的 skills/codex/ 与 skills/workbuddy/ 中维护通用 Skill 和宿主适配说明后，运行：')
box('.venv/bin/python tools/build_general_workbuddy_skill.py')
add('构建结果位于 skills/workbuddy/general-pixel-art-to-3mf/ 与 output/packages/general-pixel-art-to-3mf-workbuddy.zip。再将新包导入或同步到 WorkBuddy 的项目级与个人级目录；构建脚本本身不会自动安装。','small')
add('Skill 内部结构','sub')
add('SKILL.md 控制阶段；references/ 保存生图、预检、整理和导出规则；assets/ 包含处理后的柯基逻辑图与预览；scripts/ 包含新版整理入口。两种 3MF 转换继续复用 WorkBuddy 项目内现有工具。','small')
add('依据：本说明对应 2026-09-17 打包的 general-pixel-art-to-3mf WorkBuddy 版、general-host-adapter.md 及随包四份流程参考文件。','small')

doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=43,bottomMargin=58,title='通用像素画转 3MF - WorkBuddy 使用说明',author='Pixel3MF',pageCompression=1)
doc.build(story,onFirstPage=foot,onLaterPages=foot)
reader=PdfReader(OUT)
assert len(reader.pages)==5, f'Unexpected page count: {len(reader.pages)}'
assert all(len(page.extract_text().strip())>100 for page in reader.pages)
shutil.copyfile(OUT,ROOT/'output/packages/general-pixel-art-to-3mf-workbuddy-guide.pdf')
print(OUT)
print('Pages:',len(reader.pages))
