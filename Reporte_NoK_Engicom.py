# -*- coding: utf-8 -*-
"""Reporte NoK Engicom: extracción PDF, SPC descriptivo, dashboard y exportación."""
import io, re, zipfile, hashlib
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import pdfplumber
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

st.set_page_config(page_title='Reporte NoK | Engicom', page_icon='📊', layout='wide')
st.markdown('''<style>.block-container{padding-top:1.1rem;max-width:1600px}[data-testid="stMetric"]{background:#f2f6fa;border:1px solid #dce5ee;padding:14px;border-radius:12px}h1,h2,h3{letter-spacing:-.02em}</style>''', unsafe_allow_html=True)
COLS=['Nombre del archivo','Pieza','Leva','Apoyo','Caracteristica','Medicion','Area','Resultado','Min','Max']
APOYO_IDS=['Aux:G','1:A L','1:A R','2:C','3:D','4:E','5:B']
CHAR_APOYO=['Diametro','Roundness','Runout','Concentricity','Parallelism','Taper','Cylindricity']
CHAR_LEVA=['AngleErr',"BC-Rad'sErr",'BC-Runout','BC-Vel./10°','Ramp-MaxLift','Nose-MaxLift','Ramp+9°Vel/1°','Nose-Vel./1°','Taper','Center-Dev']
CHAR_CL=['(1) 40- 80 UPR','(2) 81-140 UPR','(3) 141-190 UPR','(4) 191-300 UPR','(5) 301-400 UPR']
CHAR_CA=['(1) 5 - 8 UPR','(2) 9 - 15 UPR','(3) 16 - 23 UPR','(4) 24 - 28 UPR','(5) 29- 45 UPR','(6) 46-70 UPR','(7) 71-140 UPR','(8) 141-215 UPR','(9) 216-270 UPR','(10) 271-300 UPR']
AS={'Aux:G':{'Diametro':(-.013,.013),'Roundness':(0,.012),'Runout':(0,.05),'Concentricity':(0,.03)},'1':{'Diametro':(-.013,.013),'Roundness':(0,.012),'Runout':(0,.03),'Concentricity':(0,.03),'Taper':(-.015,.015)},'2':{'Diametro':(-.013,.013),'Roundness':(0,.012)},'3':{'Diametro':(-.013,.013),'Roundness':(0,.012),'Runout':(0,.03),'Concentricity':(0,.03),'Parallelism':(0,.015),'Taper':(-.015,.015),'Cylindricity':(0,.03)},'4':{'Diametro':(-.013,.013),'Roundness':(0,.012),'Runout':(0,.03),'Concentricity':(0,.03),'Parallelism':(0,.015),'Taper':(-.015,.015),'Cylindricity':(0,.03)},'5':{'Diametro':(-.013,.013),'Roundness':(0,.012),'Runout':(0,.03),'Concentricity':(0,.03),'Parallelism':(0,.015),'Taper':(-.015,.015),'Cylindricity':(0,.03)},'6':{'Diametro':(-.013,.013),'Roundness':(0,.012),'Runout':(0,.03),'Concentricity':(0,.03),'Taper':(-.015,.015),'Cylindricity':(0,.03)}}
LS={ 'AngleErr':(-.25,.25),"BC-Rad'sErr":(-.038,.038),'BC-Runout':(0,.025),'BC-Vel./10°':(-.012,.012),'Ramp-MaxLift':(-.031,.031),'Nose-MaxLift':(-.025,.025),'Ramp+9°Vel/1°':(-.013,.013),'Nose-Vel./1°':(-.0033,.0033),'Taper':(-.016,.016),'Center-Dev':(-.008,.008)}
CL={'(1) 40- 80 UPR':.000325,'(2) 81-140 UPR':.00016,'(3) 141-190 UPR':.000125,'(4) 191-300 UPR':.00008,'(5) 301-400 UPR':.0001}
CA={'(1) 5 - 8 UPR':.001,'(2) 9 - 15 UPR':.00075,'(3) 16 - 23 UPR':.00095,'(4) 24 - 28 UPR':.00095,'(5) 29- 45 UPR':.000585,'(6) 46-70 UPR':.00058,'(7) 71-140 UPR':.0003,'(8) 141-215 UPR':.0003}
CF={'(1) 29 - 45 UPR':.00033,'(2) 46 -70 UPR':.00033,'(3) 71 - 140 UPR':.00016,'(4) 141 - 215 UPR':.00013,'(5) 216 - 270 UPR':.00008}

def num(v):
    try:
        s=str(v).strip().replace(',','.').replace('#','')
        return float(s) if s and s.lower() not in ('none','nan','-') else np.nan
    except Exception:return np.nan

def spec(area,apoyo,char):
    if area=='Apoyos':
        key={'Aux:G':'Aux:G','1:A L':'1','1:A R':'2','2:C':'3','3:D':'4','4:E':'5','5:B':'6'}.get(str(apoyo),'')
        return AS.get(key,{}).get(char,(np.nan,np.nan))
    if area=='Levas':return LS.get(char,(np.nan,np.nan))
    if area in ('Base Circle','Lift Area'):return (0,CL.get(char,np.nan))
    if area=='Chatter apoyos':return (0,CA.get(char,np.nan))
    return (np.nan,np.nan)

def row(file,piece,leva,apoyo,char,value,area,family=''):
    val=num(value); mn,mx=spec(area,apoyo,char); result='Nok' if '#' in str(value) else 'Ok'
    limits={'cl':CL,'ca':CA,'cf':CF}.get(family,{})
    if family and char in limits and np.isfinite(val) and (val>=limits[char] if family=='cl' else val>limits[char]):result='Nok'
    return {'Nombre del archivo':file,'Pieza':piece,'Leva':leva,'Apoyo':apoyo,'Caracteristica':char,'Medicion':val,'Area':area,'Resultado':result,'Min':mn,'Max':mx}

def parse_pdf(name,blob,piece):
    out={k:[] for k in ['Apoyos','Levas','chatter Levas','Chatter apoyos','Chatter Journal Ford']}
    try:
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            if not pdf.pages:return out,'PDF sin páginas'
            p1=pdf.pages[0].extract_text() or ''; p2=(pdf.pages[1].extract_text() or '') if len(pdf.pages)>1 else ''
    except Exception as e:return out,f'Error leyendo PDF: {e}'
    a,b,c=p1.find('MAIN JOURNALS:'),p1.find('LOBES:'),p1.find('CHATTER:')
    if a>=0 and b>=0:
        pat=re.compile(r'('+'|'.join(re.escape(x) for x in APOYO_IDS)+r')\s+([\s\d.\-#]+(?:\s+J[\d\-]+:\s+[\d.\-]+)?(?:\s+L[\d\-]+:\s+[\d.\-]+)?(?:\s+Tol:\s+[\d.\-]+)?)')
        for line in p1[a:b].splitlines():
            m=pat.match(line.strip())
            if not m:continue
            apoyo,vs=m.group(1).strip(),m.group(2).strip(); raw=[v for v in re.split(r'\s+',vs) if v and not re.match(r'J\d-\d:|J\d:',v) and v!='Tol:']
            vals={ch:None for ch in CHAR_APOYO}
            if apoyo=='1:A L' and len(raw)>=6:vals.update(dict(zip(['Diametro','Roundness','Runout','Concentricity','Taper'],[raw[i] for i in [1,2,3,4,5]])))
            elif apoyo=='5:B' and len(raw)>=7:vals.update(dict(zip(['Diametro','Roundness','Runout','Concentricity','Taper','Cylindricity'],[raw[i] for i in [1,2,3,4,5,6]])))
            else:
                # The source PDF has an extra measured-diameter column before Error.
                for i,ch in enumerate(['Diametro','Roundness','Runout','Concentricity','Parallelism','Taper','Cylindricity'],start=1):
                    if i<len(raw):vals[ch]=raw[i]
            for ch,v in vals.items():
                if v is not None:out['Apoyos'].append(row(name,piece,None,apoyo,ch,v,'Apoyos'))
    if b>=0:
        lines=p1[b:c if c>=0 else len(p1):].splitlines(); start=next((i for i,l in enumerate(lines) if l.strip().startswith('1: EXH-1')),-1)
        pat=re.compile(r'^([0-9]+):\s*[A-Z0-9-:]+\s+(.*)')
        if start>=0:
            for line in lines[start:]:
                m=pat.match(line.strip())
                if not m:continue
                vs=re.split(r'\s+',m.group(2).strip()); vs=vs[::2] if len(vs)==20 else vs
                if len(vs)==10:
                    for ch,v in zip(CHAR_LEVA,vs):out['Levas'].append(row(name,piece,m.group(1),None,ch,v,'Levas'))
    if c>=0:
        lines=p1[c:].splitlines(); start=next((i for i,l in enumerate(lines) if re.match(r'^\s*\d+:',l.strip())),-1)
        if start>=0:
            for line in lines[start:]:
                m=re.match(r'^(\d+):\s+(.*)',line.strip())
                if not m:continue
                vs=re.split(r'\s+',m.group(2).strip())
                if len(vs)!=20:continue
                for area,values in [('Base Circle',[vs[i*2] for i in range(5)]),('Lift Area',[vs[10+i*2] for i in range(5)])]:
                    for ch,v in zip(CHAR_CL,values):out['chatter Levas'].append(row(name,piece,m.group(1),None,ch,v,area,'cl'))
    if p2:
        mt=re.search(r'CHATTER:\s*-+\s*Journals\s*-+',p2)
        if mt:
            lines=p2[mt.start():].splitlines(); start=next((i for i,l in enumerate(lines) if re.match(r'^\s*\d+:',l.strip())),-1)
            ren={'1:':'1:A L','2:':'1:A R','3:':'2:C','4:':'3:D','5:':'4:E','6:':'5:B'}
            ford={'(5) 29- 45 UPR':'(1) 29 - 45 UPR','(6) 46-70 UPR':'(2) 46 -70 UPR','(7) 71-140 UPR':'(3) 71 - 140 UPR','(8) 141-215 UPR':'(4) 141 - 215 UPR','(9) 216-270 UPR':'(5) 216 - 270 UPR'}
            if start>=0:
                for line in lines[start:]:
                    m=re.match(r'^(\d+):\s+(.*)',line.strip())
                    if not m:continue
                    apoyo=ren.get(m.group(1)+':',m.group(1)); vs=[v for v in re.split(r'\s+',m.group(2).strip()) if v and v!='@UPR']
                    for i,ch in enumerate(CHAR_CA[:len(vs)//2]):
                        v=vs[i*2];out['Chatter apoyos'].append(row(name,piece,None,apoyo,ch,v,'Chatter apoyos','ca'))
                        if ch in ford:
                            fc=ford[ch]; r=row(name,piece,None,apoyo,fc,v,'Chatter Journal Ford','cf');out['Chatter Journal Ford'].append(r)
    return out,None

def expand_uploads(files):
    pdfs=[];errs=[];seen=set()
    for f in files:
        try:
            blob=f.getvalue(); candidates=[]
            if f.name.lower().endswith('.pdf'):candidates=[(f.name,blob)]
            else:
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    for info in z.infolist():
                        if not info.is_dir() and info.filename.lower().endswith('.pdf'):
                            try:candidates.append((Path(info.filename).name,z.read(info)))
                            except Exception as e:errs.append({'Archivo':info.filename,'Error':str(e)})
            for name,data in candidates:
                h=hashlib.sha256(data).hexdigest()
                if h not in seen:seen.add(h);pdfs.append((name,data))
        except Exception as e:errs.append({'Archivo':f.name,'Error':str(e)})
    return pdfs,errs

def summarize(master):
    """Resumen ejecutivo ampliado, conservando los indicadores y desgloses del archivo original."""
    if master.empty:
        return pd.DataFrame(columns=['Metrica','Valor']), pd.DataFrame(columns=['Indicador','Valor'])
    nok=master[master.Resultado.eq('Nok')]
    n=master.Pieza.nunique(); bad=nok.Pieza.nunique(); good=max(n-bad,0)
    total=len(master); nok_meas=len(nok); ok_meas=total-nok_meas
    # El original contaba las piezas NOK por componente, uniendo dimensional y chatter.
    ap_dim=master[(master.Area.eq('Apoyos')) & master.Resultado.eq('Nok')].Pieza.nunique()
    ap_chat=master[(master.Area.eq('Chatter apoyos')) & master.Resultado.eq('Nok')].Pieza.nunique()
    lev_dim=master[(master.Area.eq('Levas')) & master.Resultado.eq('Nok')].Pieza.nunique()
    lev_chat=master[(master.Area.isin(['Base Circle','Lift Area'])) & master.Resultado.eq('Nok')].Pieza.nunique()
    ap_total=set(master[(master.Area.isin(['Apoyos','Chatter apoyos'])) & master.Resultado.eq('Nok')].Pieza.unique())
    lev_total=set(master[(master.Area.isin(['Levas','Base Circle','Lift Area'])) & master.Resultado.eq('Nok')].Pieza.unique())
    regchar='(5) 301-400 UPR'
    reg=nok[nok.Caracteristica.eq(regchar)]
    nok_chars=nok.groupby('Pieza').Caracteristica.agg(lambda x:set(x)).to_dict()
    reg_pieces=set(reg.Pieza.unique())
    reg_only=sum(nok_chars.get(piece,set())=={regchar} for piece in reg_pieces)
    reg_with_other=sum(len(nok_chars.get(piece,set()))>1 for piece in reg_pieces)
    # Preserve original executive metrics and add useful measurement-level indicators.
    metrics=[
      ('Total de piezas analizadas',n),
      ('Piezas con resultado OK (todas las caracterist. OK)',good),
      ('Piezas con resultado NOK (al menos una caracterist. NOK)',bad),
      ('Porcentaje de Rechazo',round(100*bad/n,2) if n else 0),
      ('FTQ (First Time Quality)',round(100*good/n,2) if n else 0),
      ('Total de características/mediciones analizadas',total),
      ('Características con resultado OK',ok_meas),
      ('Características con resultado NOK',nok_meas),
      ('% Características OK',round(100*ok_meas/total,2) if total else 0),
      ('% Características NOK',round(100*nok_meas/total,2) if total else 0),
      ('--- DESGLOSE DE RECHAZOS POR COMPONENTE ---',None),
      ('Piezas con fallas en APOYOS (Total)',len(ap_total)),
      ('  -> Rechazo Dimensional (Pestaña Apoyos)',ap_dim),
      ('  -> Rechazo por Chatter (Pestaña Chatter apoyos)',ap_chat),
      ('Piezas con fallas en LEVAS (Total)',len(lev_total)),
      ('  -> Rechazo Dimensional (Pestaña Levas)',lev_dim),
      ('  -> Rechazo por Chatter (Pestaña chatter Levas)',lev_chat),
      ('--- DETALLE ESPECÍFICO REG 5 ---',None),
      (f'Cantidad piezas rechazadas SOLO por "{regchar}"',reg_only),
      (f'Cantidad piezas rechazadas por "{regchar}" Y otra característica',reg_with_other),
      (f'Cantidad piezas rechazadas SOLO por "{regchar}" en Lift Area',master[(master.Pieza.isin([p for p in reg_pieces if nok_chars.get(p,set())=={regchar}])) & master.Caracteristica.eq(regchar) & master.Area.eq('Lift Area') & master.Resultado.eq('Nok')].Pieza.nunique()),
      (f'Cantidad piezas rechazadas SOLO por "{regchar}" en Base Circle',master[(master.Pieza.isin([p for p in reg_pieces if nok_chars.get(p,set())=={regchar}])) & master.Caracteristica.eq(regchar) & master.Area.eq('Base Circle') & master.Resultado.eq('Nok')].Pieza.nunique()),
      ('Total de mediciones NOK',nok_meas),
      ('Porcentaje de mediciones NOK',round(100*nok_meas/total,2) if total else 0),
    ]
    s=pd.DataFrame(metrics,columns=['Metrica','Valor'])
    rs=pd.DataFrame({'Indicador':['Piezas con REG 5 NOK','Solo REG 5','REG 5 + otras características','REG 5 NOK en Base Circle','REG 5 NOK en Lift Area'],
                     'Valor':[len(reg_pieces),reg_only,reg_with_other,reg[reg.Area.eq('Base Circle')].Pieza.nunique(),reg[reg.Area.eq('Lift Area')].Pieza.nunique()]})
    return s,rs

def capability(master):
    if master.empty:return pd.DataFrame()
    d=master.dropna(subset=['Medicion']).copy(); rows=[]
    for (area,ch,mn,mx),g in d.groupby(['Area','Caracteristica','Min','Max'],dropna=False):
        x=g.Medicion.dropna(); n=len(x); mean=x.mean() if n else np.nan; sd=x.std(ddof=1) if n>1 else np.nan;pp=ppk=np.nan
        if n>1 and pd.notna(sd) and sd>0:
            if pd.notna(mn) and pd.notna(mx):pp=(mx-mn)/(6*sd);ppk=min((mx-mean)/(3*sd),(mean-mn)/(3*sd))
            elif pd.notna(mx):ppk=(mx-mean)/(3*sd)
            elif pd.notna(mn):ppk=(mean-mn)/(3*sd)
        nok=g.Resultado.eq('Nok').sum()
        rows.append({'Area':area,'Caracteristica':ch,'N':n,'Media':mean,'Desv. estándar':sd,'Mínimo':x.min(),'Máximo':x.max(),'Min':mn,'Max':mx,'NOK':int(nok),'% NOK':100*nok/n if n else np.nan,'Pp':pp,'Ppk':ppk})
    return pd.DataFrame(rows).sort_values('% NOK',ascending=False,na_position='last')

def pareto(df,col,title,topn):
    d=df[df.Resultado.eq('Nok')].groupby(col).Pieza.nunique().sort_values(ascending=False).head(topn).reset_index(name='Piezas NOK')
    if d.empty:
        fig=go.Figure(); fig.add_annotation(text='No se detectaron registros NOK para este filtro',xref='paper',yref='paper',x=.5,y=.5,showarrow=False); fig.update_layout(title=title,height=360); return fig
    d['Acumulado %']=100*d['Piezas NOK'].cumsum()/d['Piezas NOK'].sum()
    fig=go.Figure();fig.add_bar(x=d[col].astype(str),y=d['Piezas NOK'],name='Piezas NOK',marker_color='#137C8B');fig.add_scatter(x=d[col].astype(str),y=d['Acumulado %'],name='% acumulado',yaxis='y2',mode='lines+markers',line=dict(color='#E09F3E',width=3))
    fig.update_layout(title=title,xaxis_title='',yaxis_title='Piezas únicas NOK',yaxis2=dict(title='% acumulado',overlaying='y',side='right',range=[0,105]),legend=dict(orientation='h',y=1.12),height=430,margin=dict(t=70,b=80));return fig

def make_excel(dfs,master,caps,summary,reg,errors):
    b=io.BytesIO()
    with pd.ExcelWriter(b,engine='openpyxl') as w:
        for name,df in dfs.items():(df if not df.empty else pd.DataFrame(columns=COLS)).to_excel(w,index=False,sheet_name=name[:31])
        master.to_excel(w,index=False,sheet_name='Master');master[master.Resultado.eq('Nok')].to_excel(w,index=False,sheet_name='Nok')
        summary.to_excel(w,index=False,sheet_name='Resumen ejecutivo');reg.to_excel(w,index=False,sheet_name='Resumen REG 5');caps.to_excel(w,index=False,sheet_name='Pp_Ppk')
        if errors:pd.DataFrame(errors).to_excel(w,index=False,sheet_name='Errores')
        for ws in w.book.worksheets:
            ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width=min(38,max(12,max((len(str(c.value)) for c in list(col)[:250] if c.value is not None),default=12)+2))
    b.seek(0);return b.getvalue()

def make_pdf(master,summary,reg,caps,topn=15):
    """Exporta a PDF el conjunto de gráficas que se generan en las pestañas del dashboard."""
    b=io.BytesIO()
    doc=SimpleDocTemplate(b,pagesize=landscape(A4),rightMargin=12*mm,leftMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='EngicomTitle',parent=styles['Title'],fontSize=21,textColor=colors.HexColor('#15324B'),alignment=TA_CENTER,spaceAfter=5))
    styles.add(ParagraphStyle(name='ChartHeading',parent=styles['Heading2'],fontSize=13,textColor=colors.HexColor('#15324B'),spaceBefore=5,spaceAfter=5))
    story=[Paragraph('ENGICOM | REPORTE DE CALIDAD NoK',styles['EngicomTitle']),Paragraph('Dashboard ejecutivo completo · '+datetime.now().strftime('%Y-%m-%d %H:%M:%S'),styles['Normal']),Spacer(1,4*mm)]
    def addtable(df,limit=None):
        if df is None or df.empty:return
        v=df.copy() if limit is None else df.head(limit).copy()
        v=v.replace({np.nan:'—'}); data=[list(map(str,v.columns))]+[[str(x)[:70] for x in r] for r in v.to_numpy().tolist()]
        t=Table(data,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#15324B')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#CBD5E1')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F1F5F9')]),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        story.extend([t,Spacer(1,3*mm)])
    def addfig(fig,width=245*mm,height=105*mm):
        im=io.BytesIO();fig.savefig(im,format='png',dpi=145,bbox_inches='tight',facecolor='white');plt.close(fig);im.seek(0)
        story.append(Image(im,width=width,height=height));story.append(Spacer(1,3*mm))
    def addplotly_pie(good,bad):
        fig,ax=plt.subplots(figsize=(7.4,3.6)); vals=[good,bad]
        if sum(vals): ax.pie(vals,labels=['OK','NOK'],autopct='%1.1f%%',startangle=90,colors=['#159A80','#D9485F'],wedgeprops={'width':.42,'edgecolor':'white'})
        else: ax.text(.5,.5,'Sin piezas',ha='center',va='center')
        ax.set_title('Resultado por pieza');addfig(fig,175*mm,85*mm)
    def add_pareto(df,col,title):
        d=df[df.Resultado.eq('Nok')].groupby(col).Pieza.nunique().sort_values(ascending=False).head(topn)
        fig,ax=plt.subplots(figsize=(10,4.2))
        if d.empty:ax.text(.5,.5,'No se detectaron registros NOK',ha='center',va='center');ax.set_axis_off()
        else:
            sns.barplot(x=d.values,y=d.index.astype(str),ax=ax,color='#137C8B')
            ax.set_xlabel('Piezas únicas NOK');ax.set_ylabel('');ax.set_title(title)
            total=d.sum();ax2=ax.twiny();ax2.plot(d.values.cumsum()/total*100,range(len(d)),color='#E09F3E',marker='o');ax2.set_xlim(0,110);ax2.set_xlabel('% acumulado')
        fig.tight_layout();addfig(fig)
    nok=master[master.Resultado.eq('Nok')]; pieces=master.Pieza.nunique();bad=nok.Pieza.nunique();good=max(pieces-bad,0)
    story.append(Paragraph('1. Resumen ejecutivo',styles['Heading1']))
    addtable(summary)
    addplotly_pie(good,bad)
    add_pareto(master,'Caracteristica',f'Pareto por característica · Top {topn}')
    story.append(Paragraph('2. Resultado por pieza y Pareto',styles['Heading1']))
    add_pareto(master,'Pieza',f'Pareto por pieza · Top {topn}')
    for area in sorted(master.Area.dropna().astype(str).unique()):
        add_pareto(master[master.Area.astype(str).eq(area)],f'Caracteristica',f'Pareto por característica · {area} · Top {topn}')
    story.append(Paragraph('3. Indicadores REG 5 · Base Circle / Lift Area',styles['Heading1']));addtable(reg)
    story.append(Paragraph('4. Distribución, cajas e histogramas por característica',styles['Heading1']))
    for ch in sorted(master.Caracteristica.dropna().astype(str).unique()):
        g=master[master.Caracteristica.astype(str).eq(ch)].dropna(subset=['Medicion']).copy()
        if g.empty:continue
        fig,ax=plt.subplots(figsize=(10,4))
        sns.boxplot(data=g,x='Area',y='Medicion',ax=ax,color='#A7C7D7')
        sns.stripplot(data=g,x='Area',y='Medicion',ax=ax,color='#15324B',size=2,alpha=.45)
        for field,label,color in [('Min','LSL','#D97706'),('Max','USL','#DC2626')]:
            vals=g[field].dropna()
            if not vals.empty:ax.axhline(vals.iloc[0],linestyle='--',color=color,label=label)
        ax.set_title(f'Boxplot y valores individuales · {ch}');ax.set_xlabel('Área');ax.set_ylabel('Medición')
        if ax.get_legend_handles_labels()[0]:ax.legend(loc='best')
        fig.tight_layout();addfig(fig)
        fig,ax=plt.subplots(figsize=(10,3.7))
        sns.histplot(data=g,x='Medicion',hue='Area',kde=False,bins=40,element='step',stat='count',common_norm=False,ax=ax)
        ax.set_title(f'Histograma de mediciones · {ch}');ax.set_xlabel('Medición');ax.set_ylabel('Frecuencia');fig.tight_layout();addfig(fig)
    story.append(Paragraph('5. Resumen de capacidad Pp / Ppk',styles['Heading1']));addtable(caps)
    valid=caps.dropna(subset=['Ppk']).copy() if caps is not None and not caps.empty else pd.DataFrame()
    if not valid.empty:
        valid['Grupo']=valid.Area.astype(str)+' · '+valid.Caracteristica.astype(str)
        valid=valid.sort_values('Ppk')
        fig,ax=plt.subplots(figsize=(10,max(4,min(11,.28*len(valid)+1))))
        sns.barplot(data=valid,x='Ppk',y='Grupo',ax=ax,hue='Ppk',palette='RdYlGn',legend=False)
        ax.axvline(1.33,linestyle='--',color='#15324B',label='Referencia 1.33');ax.set_title('Ppk por área y característica');ax.set_xlabel('Ppk');ax.set_ylabel('');ax.legend()
        fig.tight_layout();addfig(fig)
    story.append(Paragraph('Pp/Ppk son indicadores descriptivos calculados con desviación estándar global muestral. No demuestran estabilidad del proceso ni sustituyen un estudio de capacidad aprobado. Los límites deben validarse contra la especificación controlada vigente.',styles['Italic']))
    doc.build(story);b.seek(0);return b.getvalue()

def main():
    st.title('📊 Reporte NoK | ENGICOM')
    st.caption('Calidad dimensional y chatter · Pareto · distribución · Pp/Ppk · detalle por pieza · Excel y PDF')
    with st.sidebar:
        st.header('Entrada de datos');uploads=st.file_uploader('Selecciona PDF y/o ZIP',type=['pdf','zip'],accept_multiple_files=True)
        topn=st.slider('Elementos en Pareto',5,30,15)
        st.caption('Los límites se trasladaron del código adjunto. Confírmalos contra la especificación oficial de Engicom antes de liberar decisiones de calidad.')
    if not uploads:
        st.info('Carga reportes PDF individuales o un ZIP con PDF para comenzar.')
        st.markdown('**Incluye:** extracción por pieza, identificación del archivo, OK/NOK, Pareto, boxplots, valores individuales, Pp/Ppk y exportaciones Excel/PDF.')
        return
    if st.button('🚀 Procesar reportes',type='primary',width='stretch'):
        pdfs,errors=expand_uploads(uploads)
        if not pdfs:st.error('No se encontraron PDF válidos.');return
        records={k:[] for k in ['Apoyos','Levas','chatter Levas','Chatter apoyos','Chatter Journal Ford']};prog=st.progress(0);msg=st.empty()
        for i,(name,blob) in enumerate(pdfs,1):
            msg.write(f'Procesando {i:,}/{len(pdfs):,}: {name}')
            extracted,err=parse_pdf(name,blob,i)
            if err:errors.append({'Archivo':name,'Error':err})
            for k,v in extracted.items():records[k].extend(v)
            prog.progress(i/len(pdfs))
        dfs={k:pd.DataFrame(v,columns=COLS) for k,v in records.items()}
        mainkeys=['Apoyos','Levas','chatter Levas','Chatter apoyos'];master=pd.concat([dfs[k] for k in mainkeys if not dfs[k].empty],ignore_index=True) if any(not dfs[k].empty for k in mainkeys) else pd.DataFrame(columns=COLS)
        summary,reg=summarize(master);caps=capability(master)
        st.session_state['engicom_nok']={'dfs':dfs,'master':master,'summary':summary,'reg':reg,'caps':caps,'errors':errors,'pdfs':len(pdfs)}
        msg.success(f'Procesamiento terminado: {len(pdfs):,} PDF únicos.')
    d=st.session_state.get('engicom_nok')
    if not d:return
    master=d['master'];dfs=d['dfs'];summary=d['summary'];reg=d['reg'];caps=d['caps'];errors=d['errors']
    if master.empty:
        st.warning('No se extrajeron mediciones. Revisa que los PDF contengan texto seleccionable y las secciones MAIN JOURNALS, LOBES y CHATTER.')
        if errors:st.dataframe(pd.DataFrame(errors),width='stretch')
        return
    nok=master[master.Resultado.eq('Nok')];pieces=master.Pieza.nunique();bad=nok.Pieza.nunique();good=pieces-bad
    a,b,c,e,f=st.columns(5);a.metric('Piezas analizadas',f'{pieces:,}');b.metric('Piezas OK',f'{good:,}');c.metric('Piezas NOK',f'{bad:,}');e.metric('FTQ',f'{100*good/pieces:.2f}%');f.metric('Mediciones NOK',f'{len(nok):,}')
    tabs=st.tabs(['🏁 Ejecutivo','🎯 Pareto','📦 Distribución','📐 Pp / Ppk','🔎 Reportes individuales','📤 Exportar'])
    with tabs[0]:
        l,r=st.columns([1,1.2])
        with l:
            fig=go.Figure(data=[go.Pie(labels=['OK','NOK'],values=[good,bad],hole=.62,marker_colors=['#159A80','#D9485F'])]);fig.update_layout(title='Resultado por pieza',height=360,margin=dict(t=55,b=10));st.plotly_chart(fig,width='stretch')
        with r:
            st.subheader('Resumen ejecutivo')
            summary_view=summary.copy()
            # Evita mezclar números y cadenas vacías en Valor: PyArrow no puede inferir un tipo numérico único.
            summary_view['Valor']=summary_view['Valor'].map(lambda value: '' if pd.isna(value) else str(value))
            st.dataframe(summary_view, width='stretch', hide_index=True)
            st.subheader('REG 5 · (5) 301–400 UPR');st.dataframe(reg,width='stretch',hide_index=True)
        st.subheader('Piezas con más mediciones NOK')
        pp=nok.groupby(['Pieza','Nombre del archivo']).agg(**{'Mediciones NOK':('Caracteristica','size'),'Características NOK':('Caracteristica',lambda s:', '.join(sorted(set(s))))}).reset_index().sort_values('Mediciones NOK',ascending=False)
        st.dataframe(pp.head(100),width='stretch',hide_index=True)
    with tabs[1]:
        st.plotly_chart(pareto(master,'Caracteristica',f'Pareto por característica · Top {topn}',topn),width='stretch')
        st.plotly_chart(pareto(master,'Pieza',f'Pareto por pieza · Top {topn}',topn),width='stretch')
        area=st.selectbox('Área',sorted(master.Area.dropna().astype(str).unique()));st.plotly_chart(pareto(master[master.Area.eq(area)],'Caracteristica',f'Pareto · {area}',topn),width='stretch')
    with tabs[2]:
        chars=sorted(master.Caracteristica.dropna().astype(str).unique());ch=st.selectbox('Característica',chars);df=master[master.Caracteristica.eq(ch)].dropna(subset=['Medicion'])
        if not df.empty:
            fig=px.box(df,x='Area',y='Medicion',color='Area',points='all',hover_data=['Pieza','Nombre del archivo'],title=f'Boxplot y valores individuales · {ch}')
            for col,label,color in [('Min','LSL','#D97706'),('Max','USL','#DC2626')]:
                z=df[col].dropna()
                if not z.empty:fig.add_hline(y=z.iloc[0],line_dash='dash',line_color=color,annotation_text=label)
            st.plotly_chart(fig,width='stretch')
            st.plotly_chart(px.histogram(df,x='Medicion',color='Area',marginal='box',nbins=40,title=f'Histograma · {ch}',opacity=.75),width='stretch')
            st.dataframe(df[['Pieza','Nombre del archivo','Area','Leva','Apoyo','Medicion','Min','Max','Resultado']],width='stretch',hide_index=True)
        else:st.info('Sin mediciones numéricas para esta característica.')
    with tabs[3]:
        st.caption('Pp/Ppk calculados con desviación estándar global muestral. No demuestran estabilidad; 1.33 es solo una referencia común, no un criterio aprobado aquí.')
        areas=['Todas']+sorted(caps.Area.dropna().astype(str).unique());af=st.selectbox('Filtrar área para capacidad',areas)
        cv=caps if af=='Todas' else caps[caps.Area.eq(af)]
        st.dataframe(cv.round(6),width='stretch',hide_index=True)
        valid=cv.dropna(subset=['Ppk']).copy()
        if not valid.empty:
            valid['Grupo']=valid.Area.astype(str)+' · '+valid.Caracteristica.astype(str)
            fig=px.bar(valid.sort_values('Ppk'),x='Ppk',y='Grupo',orientation='h',color='Ppk',color_continuous_scale='RdYlGn',title='Ppk por característica');fig.add_vline(x=1.33,line_dash='dash',line_color='#15324B');fig.update_layout(height=max(420,len(valid)*25));st.plotly_chart(fig,width='stretch')
    with tabs[4]:
        filt=st.multiselect('Resultado', ['Ok','Nok'],default=['Ok','Nok']);search=st.text_input('Buscar pieza o nombre de PDF')
        v=master[master.Resultado.isin(filt)].copy()
        if search:v=v[v.Pieza.astype(str).str.contains(search,case=False,na=False)|v['Nombre del archivo'].astype(str).str.contains(search,case=False,na=False)]
        st.caption(f'{len(v):,} mediciones · {v.Pieza.nunique():,} piezas');st.dataframe(v,width='stretch',hide_index=True,height=480)
        st.subheader('Registros NOK');st.dataframe(nok,width='stretch',hide_index=True,height=300)
    with tabs[5]:
        stamp=datetime.now().strftime('%Y%m%d_%H%M%S');xlsx=make_excel(dfs,master,caps,summary,reg,errors);pdf=make_pdf(master,summary,reg,caps,topn=topn)
        x,y=st.columns(2)
        x.download_button('⬇️ Descargar Excel completo',xlsx,file_name=f'Engicom_Reporte_NoK_{stamp}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',width='stretch')
        y.download_button('⬇️ Descargar dashboard PDF',pdf,file_name=f'Engicom_Dashboard_NoK_{stamp}.pdf',mime='application/pdf',width='stretch')
        st.write('Excel: hojas individuales por familia, Master, Nok, Resumen ejecutivo, Resumen REG 5 y Pp_Ppk.')
        if errors:st.warning(f'Incidencias en {len(errors)} archivo(s).');st.dataframe(pd.DataFrame(errors),width='stretch')

if __name__=='__main__':main()
