"""Optional PDF builder for the commercial deck. Requires reportlab on the build machine."""
from html.parser import HTMLParser
from pathlib import Path
import sys
from xml.sax.saxutils import escape
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

ROOT=Path(__file__).resolve().parents[1]

class Slides(HTMLParser):
    def __init__(self):
        super().__init__();self.slides=[];self.current=None;self.article=None;self.capture=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='section' and 'slide' in attrs.get('class','').split():
            self.current={'title':'','kicker':'','paragraphs':[],'articles':[],'tag':''};self.slides.append(self.current)
        if self.current is None:return
        if tag=='article':
            self.article={'title':'','paragraphs':[]};self.current['articles'].append(self.article)
        if tag=='br' and self.capture:self.capture['text'].append('\n');return
        field='title' if tag in ('h1','h2') or tag=='strong' and self.article is not None else 'kicker' if attrs.get('class')=='kicker' else 'tag' if attrs.get('class')=='tag' else 'paragraphs' if tag in ('p','li') else None
        if field:
            self.capture={'tag':tag,'field':field,'target':self.article if self.article is not None else self.current,'text':[],'bullet':tag=='li'}
    def handle_data(self,text):
        if self.capture:self.capture['text'].append(text)
    def handle_endtag(self,tag):
        if self.capture and self.capture['tag']==tag:
            c=self.capture;text=''.join(c['text']).strip()
            if c['bullet']:text='• '+text
            if c['field']=='paragraphs':c['target'][c['field']].append(text)
            else:c['target'][c['field']]=text
            self.capture=None
        if tag=='article':self.article=None
        if tag=='section':self.current=None

def build(output):
    regular=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    bold=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    font='Helvetica';strong='Helvetica-Bold'
    if regular.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont('NexoSans',str(regular)));pdfmetrics.registerFont(TTFont('NexoBold',str(bold)));font='NexoSans';strong='NexoBold'
    parser=Slides();parser.feed((ROOT/'public/presentacion.html').read_text())
    assert len(parser.slides)==8
    parser.slides[3]['articles']=[{'title':title,'paragraphs':[body]} for title,body in [('01 · Grabar','Conversación autorizada y vinculada a cliente e inmueble.'),('02 · Transcribir','Audio convertido en texto con el servicio conectado.'),('03 · Revisar','El asesor comprueba datos, acuerdos y fechas.'),('04 · Confirmar','La hoja queda en el historial y puede crear un seguimiento.')]]
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    pdf=Canvas(str(output),pagesize=(960,540));pdf.setTitle('Nexo — Presentación comercial y demo funcional');pdf.setAuthor('Nexo Inmobiliaria')
    black=HexColor('#100e12');orange=HexColor('#f4b17b');light=HexColor('#eee5df');muted=HexColor('#c5b5aa');card=HexColor('#211a24')
    def paragraph(text,x,top,width,size=15,color=light,max_height=None,bold=False):
        while True:
            style=ParagraphStyle('nexo',fontName=strong if bold else font,fontSize=size,leading=size*1.45,textColor=color)
            p=Paragraph(escape(text).replace('\n','<br/>'),style);_,h=p.wrap(width,500)
            if max_height is None or h<=max_height or size<=10:break
            size-=1
        p.drawOn(pdf,x,top-h);return h
    for number,s in enumerate(parser.slides,1):
        pdf.setFillColor(black);pdf.rect(0,0,960,540,fill=1,stroke=0)
        pdf.setFillColor(orange);pdf.setFont(strong,23);pdf.drawString(58,495,'nexo.')
        pdf.setFont(font,10);pdf.setFillColor(muted);pdf.drawRightString(902,501,'Una visita, todo su contexto.')
        pdf.setStrokeColor(HexColor('#453440'));pdf.line(58,480,902,480)
        paragraph(s['kicker'],58,454,840,10,orange,bold=True)
        top=420
        title_h=paragraph(s['title'],58,top,830,36,light,bold=True,max_height=150)
        content_top=top-title_h-24
        articles=s['articles']
        if articles:
            caption_height=0
            for text in s['paragraphs']:
                caption=Paragraph(escape(text),ParagraphStyle('measure',fontName=font,fontSize=10,leading=14.5))
                caption_height+=caption.wrap(830,500)[1]+12
            columns=len(articles);gap=16;width=(844-gap*(columns-1))/columns;height=min(208,content_top-60-caption_height)
            for i,a in enumerate(articles):
                x=58+i*(width+gap);pdf.setFillColor(card);pdf.roundRect(x,content_top-height,width,height,12,fill=1,stroke=0)
                title=paragraph(a['title'],x+18,content_top-18,width-36,17,orange,max_height=52,bold=True)
                body='\n'.join(a['paragraphs']);paragraph(body,x+18,content_top-26-title,width-36,14,light,max_height=height-title-42)
            content_top-=height+15
        for index,text in enumerate(s['paragraphs']):
            size=18 if not articles and index==0 else 10
            h=paragraph(text,58,content_top,830,size,light if size==18 else muted,max_height=max(34,content_top-62));content_top-=h+12
        if s['tag']:
            paragraph(s['tag'],58,max(90,content_top-2),825,12,orange,bold=True,max_height=40)
        pdf.setFont(font,8);pdf.setFillColor(muted);pdf.drawString(58,26,'Demo funcional · Propuesta de piloto · Condiciones a acordar')
        pdf.drawRightString(902,26,f'{number} / 8')
        pdf.linkURL('https://www.eso.org/public/images/eso1907a/',(58,8,300,20),relative=0)
        pdf.showPage()
    pdf.save()
    print(f'PDF creado: {output.name}, 8 diapositivas')

if __name__=='__main__':build(sys.argv[1] if len(sys.argv)>1 else ROOT/'Nexo-Presentacion.pdf')
