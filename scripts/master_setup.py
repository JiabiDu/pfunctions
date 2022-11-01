#!/usr/bin/env python3
from pylib import *
close("all")

p=zdata(); p.flag={}  #parameters
p.begin_time =  datenum(2018,1,1)
p.end_time   =  datenum(2019,1,1)
p.grid_dir   = '../../Grids/V1b'
p.tide_dir       = r'/sciclone/data10/wangzg/FES2014'   #FES2014 database '
p.hycom_dir  = '../../Observations/hycom/Data/'
p.flow_dir   = '../../Observations/usgs_flow/npz/'
p.temp_dir   = '../../Observations/usgs_temp/npz/'
p.sflux_dir  = '../sflux'
p.setup_dir  = '../setup_files'
p.flag['*.gr3']          =       0    
p.flag['tvd.prop']       =       0
p.flag['bctides.in']     =       0
p.flag['hotstart.nc']    =       0
p.flag['elev2D.th.nc']   =       0
p.flag['TEM_3D.th.nc']   =       0
p.flag['SAL_3D.th.nc']   =       0
p.flag['uv3D.th.nc']     =       1
p.flag['TEM_nu.nc']      =       1
p.flag['SAL_nu.nc']      =       1
p.flag['source_sink.in'] =       1
p.flag['vsource.th']     =       1
p.flag['msource.th']     =       1
p.flag['sflux']          =       1
p.flag['check']          =       1
p.flag['run']            =       1  #run the model on sciclone
#%% ===========================================================================
# copy grid files
#==============================================================================
p.grd='grid.npz'
for fname in ['hgrid.gr3','hgrid.ll','vgrid.in','grid.npz']:
    print('writing '+fname)
    sname=os.path.relpath(os.path.realpath('{}/{}'.format(p.grid_dir,fname)))
    if not fexist(sname): sys.exit('{}/{} not exist'.format(p.grid_dir,fname))
    if os.path.islink(fname) or (fexist(fname) and sname!=fname): os.remove(fname)
    if sname!=fname: os.symlink(sname,fname)
gd=loadz(p.grd).hgrid

#%% ===========================================================================
# generating gr3 files
#==============================================================================
if p.flag['*.gr3']==1:
    vars={'albedo':0.15,'diffmin':1e-6,'diffmax':1e-2,'drag':2.5e-3,'manning':1.6e-2,
            'shapiro':5e-1,'watertype':1.0,'windrot_geo2proj':0.0,'xlsc':5e-1}
    for var in vars:
        print(f'writing {var}.gr3 with value of {vars[var]}')
        gd.write_hgrid(f'{var}.gr3',value=vars[var])

    print('writing SAL_nudge.gr3')
    miny=gd.y.min()
    maxx=gd.x.max()
    dis=c_[maxx-gd.x,gd.y-miny].min(axis=1)
    pvi=2.1e-5*(0.5-dis)/0.5
    pvi[pvi<0]=0
    gd.write_hgrid(f'SAL_nudge.gr3',value=pvi)
    os.system('ln -sf SAL_nudge.gr3 TEM_nudge.gr3')

if p.flag['tvd.prop']==1:
    #generate tvd.prop
    print('write tvd.prop')
    gd.write_prop(fname='tvd.prop',value=ones(gd.ne),fmt='{:1d}')
#%% ===========================================================================
# generating bctides.in
#==============================================================================
if p.flag['bctides.in']==1:
    #---------------------------------------------------------------------
    #input
    #---------------------------------------------------------------------
    tnames=['O1','K1','Q1','P1','M2','S2','K2','N2']
    tmp=num2date(p.begin_time)
    StartT=[tmp.year,tmp.month,tmp.day,tmp.hour]
    nday=p.begin_time-p.end_time  #number of days
    ibnds=[1,]           #order of open boundaries (starts from 1)
    flags=[[5,5,4,4],]   #SCHISM bnd flags for each boundary
    Z0=0.0               #add Z0 constant if Z0!=0.0
    bdir=p.tide_dir
    
    #---------------------------------------------------------------------
    #read bndinfo, amp, freq, nodal factor and tear
    #---------------------------------------------------------------------    
    #get tidal amplitude and frequency
    amp=[]; freq=[]; ts=loadz('{}/tide_fac_const/tide_fac_const.npz'.format(bdir))
    for tname in tnames: 
        sind=nonzero(ts.name==tname.upper())[0][0]
        amp.append(ts.amp[sind]); freq.append(ts.freq[sind])
    
    #get nodal factor
    tdir='{}/tide_fac_improved'.format(bdir)
    fid=open('./tide_fac.in','w+'); fid.write('{}\n{} {} {} {}\n0\n'.format(nday,*StartT[::-1])); fid.close()
    os.system('ifort -o tide_fac_improved {}/tf_main.f90 {}/tf_selfe.f90; ./tide_fac_improved <tide_fac.in'.format(tdir,tdir))
    
    nodal=[]; tear=[]  #read nodal factor 
    for tname in tnames:
        lines=[i for i in open('./tide_fac.out','r').readlines() if len(i.split())==3]
        line=[i for i in lines if i.strip().startswith(tname.upper())][0]
        nodal.append(float(line.strip().split()[1]))
        tear.append(float(line.strip().split()[2]))
    os.system('rm tide_fac_improved tide_fac.in tide_fac.out')
    
    #---------------------------------------------------------------------
    #write bctides.in
    #---------------------------------------------------------------------
    fid=open('bctides.in','w+')
    fid.write('!{:02}/{:02}/{:4} {:02}:00:00 UTC\n'.format(*array(StartT)[array([1,2,0,3])]))
    
    #tidal potential, and frequency
    fid.write(' {:d}  50.000 !number of earth tidal potential, cut-off depth for applying tidal potential\n'.format(len(tnames)))
    for i,tname in enumerate(tnames): fid.write('{}\n{} {:<.6f}  {:<.9e}  {:7.5f}  {:.2f}\n'.format(tname,tname[1],amp[i],freq[i],nodal[i],tear[i])) 
    fid.write('{} !nbfr\n'.format(len(tnames)+int(Z0!=0)))
    if Z0!=0: fid.write('Z0\n  0.0 1.0 0.0\n')
    for i,tname in enumerate(tnames): fid.write('{}\n  {:<.9e}  {:7.5f}  {:.2f}\n'.format(tname,freq[i],nodal[i],tear[i])) 
    fid.write('{} !nope\n'.format(gd.nob))
    
    #write tidal harmonic for each boundary
    for i,ibnd in enumerate(ibnds):
        fstr='{} '+'{} '*len(flags[i])+'!ocean\n'
        fid.write(fstr.format(gd.nobn[ibnd-1],*flags[i]))
    
        #get bundary lon&lat, and interpolate for the amp and pha
        nobn=gd.nobn[ibnd-1]; sind=gd.iobn[ibnd-1]; xi=mod(gd.x[sind]+360,360); yi=gd.y[sind]; ap=[]
        for m,tname in enumerate(tnames): 
            print('compute amp. and pha. for tide {} of boundary: {}'.format(tname,i+1))
            api=[]
            for n in arange(3):  
                if n==0: fname='{}/fes2014b_elevations_extrapolated/ocean_tide_extrapolated/{}.nc'.format(bdir,tname.lower()); an,pn='amplitude','phase'
                if n==1: fname='{}/eastward_velocity/{}.nc'.format(bdir,tname.lower()); an,pn='Ua','Ug'
                if n==2: fname='{}/northward_velocity/{}.nc'.format(bdir,tname.lower());an,pn='Va','Vg'
                C=ReadNC(fname,1); lon=array(C.variables['lon'][:]); lat=array(C.variables['lat'][:])
                amp0=array(C.variables[an][:])/100; pha0=array(C.variables[pn][:]); C.close()
                fpn=pha0<0; pha0[fpn]=pha0[fpn]+360
                dxs=unique(diff(lon)); dys=unique(diff(lat))
                if len(dxs)!=1 or len(dys)!=1: sys.exit('{}: lon,lat not uniform specified'.format(fname))
                dx=dxs[0]; dy=dys[0]
    
                #get interp index (todo, if lon&lat not uniformal interval, do loop to find the right index)
                idx=floor((xi-lon[0])/dx).astype('int'); sind=nonzero((lon[idx]-xi)>0)[0]; idx[sind]=idx[sind]-1
                idy=floor((yi-lat[0])/dy).astype('int'); sind=nonzero((lat[idy]-yi)>0)[0]; idy[sind]=idy[sind]-1 
                xrat=(xi-lon[idx])/(lon[idx+1]-lon[idx]); yrat=(yi-lat[idy])/(lat[idy+1]-lat[idy])
                if sum((xrat>1)|(xrat<0)|(yrat>1)|(yrat<0))!=0: sys.exit('xrat or yrat >1 or <0')
    
                #interp for amp,pha
                apii=[]
                for k in arange(2): 
                    if k==0: v0=c_[amp0[idy,idx],amp0[idy,idx+1],amp0[idy+1,idx],amp0[idy+1,idx+1]].T; vm=100
                    if k==1: v0=c_[pha0[idy,idx],pha0[idy,idx+1],pha0[idy+1,idx],pha0[idy+1,idx+1]].T; vm=370
                    vmax=v0.max(axis=0); vmin=v0.min(axis=0)
                    if k==1: #deal with phase jump
                       for kk in nonzero(abs(vmax-vmin)>180)[0]: 
                           fpn=abs(v0[:,kk]-vmax[kk])>180; v0[fpn,kk]=v0[fpn,kk]+360
                    v1=v0[0]*(1-xrat)+v0[1]*xrat; v2=v0[2]*(1-xrat)+v0[3]*xrat; apiii=v1*(1-yrat)+v2*yrat
                    sind=nonzero((vmax>vm)*(vmin<=vm)*(vmin>=0))[0]; apiii[sind]=vmin[sind]
                    if sum((vmax>vm)*((vmin>vm)|(vmin<0)))!=0: sys.exit('All junks for amp or pha')
                    apii.append(apiii)
                api.append(apii)
            ap.append(api)
        ap=array(ap).transpose([1,0,3,2])
    
        #write tidal amp and pha for elev 
        if Z0!=0: fid.write('Z0\n'); [fid.write('{} 0.0\n'.format(Z0)) for i in arange(nobn)]
        for m,tname in enumerate(tnames):  
            fid.write('{}\n'.format(tname.lower()))
            for k in arange(nobn):
                fid.write('{:8.6f} {:.6f}\n'.format(*ap[0,m,k]))
    
        #write tidal amp and pha for uv
        if Z0!=0: fid.write('Z0\n'); [fid.write('0.0 0.0 0.0 0.0\n') for i in arange(nobn)]
        for m,tname in enumerate(tnames): 
            fid.write('{}\n'.format(tname.lower()))
            for k in arange(nobn):
                fid.write('{:8.6f} {:.6f} {:8.6f} {:.6f}\n'.format(*ap[1,m,k],*ap[2,m,k]))
    fid.write('1 !temperature relax\n')
    fid.write('1 !salinity relax\n')
    fid.close()
    #to be revised if river boundary is included. 

#%% ===========================================================================
# generating hotstart.nc
#==============================================================================
if p.flag['hotstart.nc']:
    #------------------------------------------------------------------------------
    #input
    #------------------------------------------------------------------------------
    StartT=p.begin_time
    dir_hycom=p.hycom_dir #'../../Observations/hycom/Data/'
    
    #------------------------------------------------------------------------------
    #interpolate hycom data to boundary
    #------------------------------------------------------------------------------
    #variables to be interpolated
    svars=['water_temp','salinity']
    mvars=['temp','salt']
    
    #find hycom file
    fnames=array([i for i in os.listdir(dir_hycom) if i.endswith('.nc')])
    mti=array([datenum(*array(i.replace('.','_').split('_')[1:5]).astype('int')) for i in fnames])
    if abs(mti-StartT).min()>1: system.exit('the availabe hycom file is too far away from the StartT')
    fpt=nonzero(abs(mti-StartT)==min(abs(mti-StartT)))[0][0]; fname=fnames[fpt]
    
    #read hgrid
    gd=loadz(p.grd).hgrid; vd=loadz(p.grd).vgrid; gd.x,gd.y=gd.lon,gd.lat
    ne,np,ns,nvrt=gd.ne,gd.np,gd.ns,vd.nvrt
    
    #get node xyz
    lxi=gd.x%360; lyi=gd.y; lzi0=abs(vd.compute_zcor(gd.dp)).T
    
    #get hycom time, xyz
    C=ReadNC('{}/{}'.format(dir_hycom,fname),1); #print(fname)
    ctime=array(C.variables['time'])/24+datenum(2000,1,1); sx=array(C.variables['lon'][:])%360
    sy=array(C.variables['lat'][:]); sz=array(C.variables['depth'][:])
    fpz=lzi0>=sz.max(); lzi0[fpz]=sz.max()-1e-6
    
    #check data; some abnormal may occurs
    C2=ReadNC('{}/{}'.format(dir_hycom,fname))
    if C2.water_temp.val.min()<0 or C2.water_temp.val.max()>40 or abs(C2.surf_el.val).max()>2 or C2.salinity.val.min()<0 or C2.salinity.val.max()>40:
        sys.exit('abnormal value in ',fname)
        
    #interp for ST
    S=zdata(); [exec('S.{}=[]'.format(i)) for i in mvars]
    for k in arange(nvrt):
        lzi=lzi0[k]; bxyz=c_[lxi,lyi,lzi]
    
        #get interp index
        idx=((lxi[:,None]-sx[None,:])>=0).sum(axis=1)-1; ratx=(lxi-sx[idx])/(sx[idx+1]-sx[idx])
        idy=((lyi[:,None]-sy[None,:])>=0).sum(axis=1)-1; raty=(lyi-sy[idy])/(sy[idy+1]-sy[idy])
        idz=((lzi[:,None]-sz[None,:])>=0).sum(axis=1)-1; ratz=(lzi-sz[idz])/(sz[idz+1]-sz[idz])
    
        #for each variable
        for m,svar in enumerate(svars):
            print('hotstart.nc interp for variable, layer:',svar,k)
            mvar=mvars[m]
            exec("cv=array(C.variables['{}'][0])".format(svar))
            v0=array([cv[idz,idy,idx],cv[idz,idy,idx+1],cv[idz,idy+1,idx],cv[idz,idy+1,idx+1],
                  cv[idz+1,idy,idx],cv[idz+1,idy,idx+1],cv[idz+1,idy+1,idx],cv[idz+1,idy+1,idx+1]])
    
            #remove nan pts
            for n in arange(8):
                fpn=abs(v0[n])>1e3
                v0[n,fpn]=sp.interpolate.griddata(bxyz[~fpn,:],v0[n,~fpn],bxyz[fpn,:],'nearest',rescale=True)
    
            v11=v0[0]*(1-ratx)+v0[1]*ratx;  v12=v0[2]*(1-ratx)+v0[3]*ratx; v1=v11*(1-raty)+v12*raty
            v21=v0[4]*(1-ratx)+v0[5]*ratx;  v22=v0[6]*(1-ratx)+v0[7]*ratx; v2=v21*(1-raty)+v22*raty
            vi=v1*(1-ratz)+v2*ratz
    
            #save
            exec('S.{}.append(vi)'.format(mvar))
    [exec('S.{}=array(S.{})'.format(i,i)) for i in mvars]
    
    #------------------------------------------------------------------------------
    #creat netcdf
    #------------------------------------------------------------------------------
    tr_nd=r_[S.temp[None,...],S.salt[None,...]].T; tr_el=tr_nd[gd.elnode[:,:3]].mean(axis=1)
    
    nd=zdata(); nd.file_format='NETCDF4'
    nd.dimname=['node','elem','side','nVert','ntracers','one']; nd.dims=[np,ne,ns,nvrt,2,1]
    
    #--time step, time, and time series----
    nd.vars=['time','iths','ifile','idry_e','idry_s','idry','eta2','we','tr_el',
      'tr_nd','tr_nd0','su2','sv2','q2','xl','dfv','dfh','dfq1','dfq2','nsteps_from_cold','cumsum_eta']
    
    vi=zdata(); vi.dimname=('one',); vi.val=array(0.0); nd.time=vi 
    vi=zdata(); vi.dimname=('one',); vi.val=array(0).astype('int'); nd.iths=vi  
    vi=zdata(); vi.dimname=('one',); vi.val=array(1).astype('int'); nd.ifile=vi 
    vi=zdata(); vi.dimname=('one',); vi.val=array(0).astype('int'); nd.nsteps_from_cold=vi 
    
    vi=zdata(); vi.dimname=('elem',); vi.val=zeros(ne).astype('int32'); nd.idry_e=vi #idry_e
    vi=zdata(); vi.dimname=('side',); vi.val=zeros(ns).astype('int32'); nd.idry_s=vi #idry_s
    vi=zdata(); vi.dimname=('node',); vi.val=zeros(np).astype('int32'); nd.idry=vi   #idry
    vi=zdata(); vi.dimname=('node',); vi.val=zeros(np); nd.eta2=vi                   #eta2
    vi=zdata(); vi.dimname=('node',); vi.val=zeros(np); nd.cumsum_eta=vi             #cumsum_eta
    
    vi=zdata(); vi.dimname=('elem','nVert'); vi.val=zeros([ne,nvrt]); nd.we=vi   #we
    vi=zdata(); vi.dimname=('side','nVert'); vi.val=zeros([ns,nvrt]); nd.su2=vi  #su2
    vi=zdata(); vi.dimname=('side','nVert'); vi.val=zeros([ns,nvrt]); nd.sv2=vi  #sv2
    vi=zdata(); vi.dimname=('node','nVert'); vi.val=zeros([np,nvrt]); nd.q2=vi   #q2
    vi=zdata(); vi.dimname=('node','nVert'); vi.val=zeros([np,nvrt]); nd.xl=vi   #xl
    vi=zdata(); vi.dimname=('node','nVert'); vi.val=zeros([np,nvrt]); nd.dfv=vi  #dfv
    vi=zdata(); vi.dimname=('node','nVert'); vi.val=zeros([np,nvrt]); nd.dfh=vi  #dfh
    vi=zdata(); vi.dimname=('node','nVert'); vi.val=zeros([np,nvrt]); nd.dfq1=vi #dfq1
    vi=zdata(); vi.dimname=('node','nVert'); vi.val=zeros([np,nvrt]); nd.dfq2=vi #dfq2
    
    vi=zdata(); vi.dimname=('elem','nVert','ntracers'); vi.val=tr_el; nd.tr_el=vi  #tr_el
    vi=zdata(); vi.dimname=('node','nVert','ntracers'); vi.val=tr_nd; nd.tr_nd=vi  #tr_nd
    vi=zdata(); vi.dimname=('node','nVert','ntracers'); vi.val=tr_nd; nd.tr_nd0=vi #tr_nd0
    if tr_el.min()<-10 or tr_nd.min()<-10:
        sys.exit('min value in tracer is less than -10')
    for itr in [0,1]:
        print(f'min and max for tracer #{itr} on node: ',tr_nd[:,:,itr].min(),tr_nd[:,:,itr].max())
        print(f'min and max for tracer #{itr} on elem: ',tr_el[:,:,itr].min(),tr_el[:,:,itr].max())
    WriteNC('hotstart.nc',nd)

#%%============================================================================
# generating ocean boundary file based on hycom
#==============================================================================
if 1 in [p.flag[fname] for fname in ['elev2D.th.nc','TEM_3D.th.nc','SAL_3D.th.nc','uv3D.th.nc']]:
    StartT=p.begin_time; EndT=p.end_time; dt=1/8
    dir_hycom=p.hycom_dir
    iLP=1; fc=0.5  #iLP=1: remove tidal signal with cutoff frequency fc (day)
    ifix=0  #ifix=0: fix hycom nan 1st, then interp;  ifix=1: interp 1st, then fixed nan
    #------------------------------------------------------------------------------
    #interpolate hycom data to boundary
    #------------------------------------------------------------------------------
    mtime=arange(StartT,EndT+dt,dt); nt=len(mtime)
    
    #variables for each files
    snames=['elev2D.th.nc','TEM_3D.th.nc','SAL_3D.th.nc','uv3D.th.nc']
    svars=['surf_el','water_temp','salinity',['water_u','water_v']] #variables in hycom
    mvars=['elev','temp','salt',['u','v']] #varialbes in schism
    
    #find all hycom files
    fnames=array([i for i in os.listdir(dir_hycom) if i.endswith('.nc')])
    mti=array([datenum(*array(i.replace('.','_').split('_')[1:5]).astype('int')) for i in fnames])
    fpt=(mti>=(StartT-1))*(mti<(EndT+1)); fnames=fnames[fpt]; mti=mti[fpt]
    sind=argsort(mti); mti=mti[sind]; fnames=fnames[sind]
    if mti.min()>StartT or mti.max()<EndT: system.exit('the availabe range of hycom file is not enough')
    
    #read hgrid
    gd=loadz(p.grd).hgrid; vd=loadz(p.grd).vgrid; gd.x,gd.y=gd.lon,gd.lat; nvrt=vd.nvrt
    
    #get bnd node xyz
    bind=gd.iobn[0]; nobn=gd.nobn[0]
    lxi0=gd.x[bind]%360; lyi0=gd.y[bind]; bxy=c_[lxi0,lyi0] #for 2D
    lxi=tile(lxi0,[nvrt,1]).T.ravel(); lyi=tile(lyi0,[nvrt,1]).T.ravel() #for 3D
    if vd.ivcor==2:
        lzi=abs(compute_zcor(vd.sigma,gd.dp[bind],ivcor=2,vd=vd)).ravel()
    else:
        lzi=abs(compute_zcor(vd.sigma[bind],gd.dp[bind])).ravel();
    bxyz=c_[lxi,lyi,lzi]
    sx0,sy0,sz0=None,None,None
    
    #for each variables
    for n,sname in enumerate(snames):
        if p.flag[sname]==0: continue
        svar=svars[n]; mvar=mvars[n]
        if isinstance(svar,str): svar=[svar]; mvar=[mvar]
    
        #interp in space
        S=zdata(); S.time=[]
        [exec('S.{}=[]'.format(i)) for i in mvar]
        for m,fname in enumerate(fnames):
            C=ReadNC('{}/{}'.format(dir_hycom,fname),1); 
            if m%240==0 or m==len(fnames)-1: print(sname,fname)
            #check data; some abnormal may occurs
            C2=ReadNC('{}/{}'.format(dir_hycom,fname))
            if C2.water_temp.val.min()<0 or C2.water_temp.val.max()>40 or abs(C2.surf_el.val).max()>2 or C2.salinity.val.min()<0 or C2.salinity.val.max()>40:
                print('abnormal value in ',fname,'; will skip this file')
                continue
            ctime=array(C.variables['time'])/24+datenum(2000,1,1); sx=array(C.variables['lon'][:])%360
            sy=array(C.variables['lat'][:]); sz=array(C.variables['depth'][:]); nz=len(sz)
            fpz=lzi>=sz.max(); lzi[fpz]=sz.max()-1e-6
            # update nz
            nz=nz-sum(sz>lzi.max()) #do not use hycom layer that has depth larger than the maximum depth in the model domain
            
            if not array_equal(sx,sx0)*array_equal(sy,sy0)*array_equal(sz,sz0): #if x,y,z of hycom is changed
                #get interp index for HYCOM data
                if ifix==0:
                    sxi,syi=meshgrid(sx,sy); sxy=c_[sxi.ravel(),syi.ravel()];
                    cvs=array(C.variables['water_temp'][0]); sindns=[]; sindps=[]
                    for ii in arange(nz):
                        print('computing HYCOM interpation index: level={}/{}'.format(ii+1,nz))
                        cv=cvs[ii]; ds=cv.shape; cv=cv.ravel()
                        fpn=abs(cv)>1e3; sindn=nonzero(fpn)[0]; sindr=nonzero(~fpn)[0]; sindp=sindr[near_pts(sxy[sindn],sxy[sindr])]
                        sindns.append(sindn); sindps.append(sindp)
    
                #get interp index for pts
                sx0=sx[:]; sy0=sy[:]; sz0=sz[:]; print('get new interp indices: {}'.format(fname))
                idx0=((lxi0[:,None]-sx0[None,:])>=0).sum(axis=1)-1; ratx0=(lxi0-sx0[idx0])/(sx0[idx0+1]-sx0[idx0])
                idy0=((lyi0[:,None]-sy0[None,:])>=0).sum(axis=1)-1; raty0=(lyi0-sy0[idy0])/(sy0[idy0+1]-sy0[idy0])
    
                idx=((lxi[:,None]-sx0[None,:])>=0).sum(axis=1)-1; ratx=(lxi-sx0[idx])/(sx0[idx+1]-sx0[idx])
                idy=((lyi[:,None]-sy0[None,:])>=0).sum(axis=1)-1; raty=(lyi-sy0[idy])/(sy0[idy+1]-sy0[idy])
                idz=((lzi[:,None]-sz0[None,:])>=0).sum(axis=1)-1; ratz=(lzi-sz0[idz])/(sz0[idz+1]-sz0[idz])
    
            S.time.extend(ctime)
            for i, cti in enumerate(ctime):
                for k,svari in enumerate(svar):
                    exec("cv=array(C.variables['{}'][{}])".format(svari,i)); mvari=mvar[k]
    
                    #interp in space
                    if mvari=='elev':
                        #remove HYCOM nan pts
                        if ifix==0:
                            sindn,sindp=sindns[0],sindps[0]
                            cv=cv.ravel(); fpn=(abs(cv[sindn])>1e3)*(abs(cv[sindp])<1e3); cv[sindn]=cv[sindp]; fpn=abs(cv)>1e3 #init fix
                            if sum(fpn)!=0: fni=nonzero(fpn)[0]; fri=nonzero(~fpn)[0]; fpi=fri[near_pts(sxy[fni],sxy[fri])]; cv[fni]=cv[fpi] #final fix
                            #fpn=abs(cv.ravel())>1e3; cv.ravel()[fpn]=sp.interpolate.griddata(sxy[~fpn,:],cv.ravel()[~fpn],sxy[fpn,:],'nearest') #old method
                            cv=cv.reshape(ds)
    
                        #find parent pts
                        v0=array([cv[idy0,idx0],cv[idy0,idx0+1],cv[idy0+1,idx0],cv[idy0+1,idx0+1]])
    
                        #remove nan in parent pts
                        if ifix==1:
                            for ii in arange(4):fpn=abs(v0[ii])>1e3; v0[ii,fpn]=sp.interpolate.griddata(bxy[~fpn,:],v0[ii,~fpn],bxy[fpn,:],'nearest')
    
                        #interp
                        v1=v0[0]*(1-ratx0)+v0[1]*ratx0;  v2=v0[2]*(1-ratx0)+v0[3]*ratx0
                        vi=v1*(1-raty0)+v2*raty0
    
                    else:
                        #remove HYCOM nan pts
                        if ifix==0:
                            for ii in arange(nz):
                                sindn,sindp=sindns[ii],sindps[ii]
                                cvi=cv[ii].ravel(); fpn=(abs(cvi[sindn])>1e3)*(abs(cvi[sindp])<1e3); cvi[sindn]=cvi[sindp]; fpn=abs(cvi)>1e3 #init fix
                                if sum(fpn)!=0: fni=nonzero(fpn)[0]; fri=nonzero(~fpn)[0]; fpi=fri[near_pts(sxy[fni],sxy[fri])]; cvi[fni]=cvi[fpi] #final fix
                                #fpn=abs(cv[ii].ravel())>1e3; cv[ii].ravel()[fpn]=sp.interpolate.griddata(sxy[~fpn,:],cv[ii].ravel()[~fpn],sxy[fpn,:],'nearest') #old method
    
                        v0=array([cv[idz,idy,idx],cv[idz,idy,idx+1],cv[idz,idy+1,idx],cv[idz,idy+1,idx+1],
                                  cv[idz+1,idy,idx],cv[idz+1,idy,idx+1],cv[idz+1,idy+1,idx],cv[idz+1,idy+1,idx+1]])
    
                        #remove nan in parent pts
                        if ifix==1:
                            for ii in arange(8): fpn=abs(v0[ii])>1e3; v0[ii,fpn]=sp.interpolate.griddata(bxyz[~fpn,:],v0[ii,~fpn],bxyz[fpn,:],'nearest',rescale=True)
    
                        v11=v0[0]*(1-ratx)+v0[1]*ratx;  v12=v0[2]*(1-ratx)+v0[3]*ratx; v1=v11*(1-raty)+v12*raty
                        v21=v0[4]*(1-ratx)+v0[5]*ratx;  v22=v0[6]*(1-ratx)+v0[7]*ratx; v2=v21*(1-raty)+v22*raty
                        vi=v1*(1-ratz)+v2*ratz
    
                    #save data
                    exec('S.{}.append(vi)'.format(mvari))
            C.close();
        S.time=array(S.time); [exec('S.{}=array(S.{})'.format(i,i)) for i in mvar]
    
        #interp in time
        for mvari in mvar:
            exec('vi=S.{}'.format(mvari))
            svi=interpolate.interp1d(S.time,vi,axis=0)(mtime)
            if iLP==1: svi=lpfilt(svi,dt,fc) #low-pass
            exec('S.{}=svi'.format(mvari))
        S.time=mtime
    
        #reshape the data, and save
        [exec('S.{}=S.{}.reshape([{},{},{}])'.format(i,i,nt,nobn,nvrt)) for i in mvar if i!='elev']
    
        #--------------------------------------------------------------------------
        #create netcdf
        #--------------------------------------------------------------------------
        nd=zdata(); nd.file_format='NETCDF4'
    
        #define dimensions
        nd.dimname=['nOpenBndNodes', 'nLevels', 'nComponents', 'one', 'time']
        if sname=='elev2D.th.nc':
            snvrt=1; ivs=1; vi=S.elev[...,None,None] + 0.2
        elif sname=='uv3D.th.nc':
            snvrt=nvrt; ivs=2; vi=c_[S.u[...,None],S.v[...,None]]
        elif sname in ['TEM_3D.th.nc','SAL_3D.th.nc']:
            snvrt=nvrt; ivs=1; exec('vi=S.{}[...,None]'.format(mvar[0]))
        nd.dims=[nobn,snvrt,ivs,1,nt]
    
        # print(mvar,nd.dims,vi.shape)
        if vi.min()<-10:
            ablay=unique(nonzero(vi<-10)[2])
            print('value <-10 occurs in layers ',ablay)
            print('manuualy asgin the bottom layer with the value of layer above')
            for ilay in ablay:
                vi[:,:,ilay,:]=vi[:,:,ablay[-1]+1,:] #use the layer above the abnormal layers
            if vi.min()<-10: sys.exit('min value less than -10')
        print(sname,'min and max value: ',vi.min(),vi.max())
        #--time step, time, and time series----
        nd.vars=['time_step', 'time', 'time_series']
        nd.time_step=zdata()
        nd.time_step.attrs=['long_name'];nd.time_step.long_name='time step in seconds'
        nd.time_step.dimname=('one',); nd.time_step.val=array(dt*86400)
    
        nd.time=zdata()
        nd.time.attrs=['long_name'];nd.time.long_name='simulation time in seconds'
        nd.time.dimname=('time',); nd.time.val=(S.time-S.time[0])*86400
    
        nd.time_series=zdata()
        nd.time_series.attrs=[]
        nd.time_series.dimname=('time','nOpenBndNodes','nLevels','nComponents')
        nd.time_series.val=vi.astype('float32')
        
        WriteNC(sname,nd)
        print(f'Finish writing {sname}')

#%%===========================================================================
# nudging nc files
#=============================================================================
if p.flag['TEM_nu.nc']==1 or p.flag['SAL_nu.nc']==1:
    StartT=p.begin_time; EndT=p.end_time; dt=1
    dir_hycom=p.hycom_dir
    iLP=1; fc=0.5  #iLP=1: remove tidal signal with cutoff frequency fc (day)
    
    ifix=0  #ifix=0: fix hycom nan 1st, then interp;  ifix=1: interp 1st, then fixed nan
    #------------------------------------------------------------------------------
    #interpolate hycom data to nudge region 
    #------------------------------------------------------------------------------
    mtime=arange(StartT,EndT+dt,dt); nt=len(mtime)
    
    #variables for each files
    snames=['TEM_nu.nc','SAL_nu.nc']
    svars=['water_temp','salinity']
    mvars=['temp','salt']
    
    #find all hycom files
    fnames=array([i for i in os.listdir(dir_hycom) if i.endswith('.nc')])
    mti=array([datenum(*array(i.replace('.','_').split('_')[1:5]).astype('int')) for i in fnames])
    fpt=(mti>=(StartT-1))*(mti<(EndT+1)); fnames=fnames[fpt]; mti=mti[fpt]
    sind=argsort(mti); mti=mti[sind]; fnames=fnames[sind]
    if mti.min()>StartT or mti.max()<EndT: system.exit('the available coverage of hycom data is not enough')
    #read hgrid
    gd=loadz(p.grd).hgrid; vd=loadz(p.grd).vgrid; gd.x,gd.y=gd.lon,gd.lat; nvrt=vd.nvrt
    
    #for each variables
    for n,[sname,svar,mvar] in enumerate(zip(snames,svars,mvars)):
        if p.flag[sname]==0: continue
        if isinstance(svar,str): svar=[svar]; mvar=[mvar]
        
        #get nudge xyz
        gdn=read_schism_hgrid('{}_nudge.gr3'.format(sname.split('_')[0])); gdn.compute_ctr()
        bind=unique(gdn.elnode[gdn.dpe!=0,:].ravel()); bind=bind[bind>=0]; nobn=len(bind)
        lxi0=gd.x[bind]%360; lyi0=gd.y[bind]; bxy=c_[lxi0,lyi0] #for 2D
        lxi=tile(lxi0,[nvrt,1]).T.ravel(); lyi=tile(lyi0,[nvrt,1]).T.ravel() #for 3D
        if vd.ivcor==2:
            lzi=abs(compute_zcor(vd.sigma,gd.dp[bind],ivcor=2,vd=vd)).ravel()
        else:
            lzi=abs(compute_zcor(vd.sigma[bind],gd.dp[bind])).ravel();
        bxyz=c_[lxi,lyi,lzi]
        sx0,sy0,sz0=None,None,None
    
        #interp in space
        S=zdata(); S.time=[]
        [exec('S.{}=[]'.format(i)) for i in mvar]
        for m,fname in enumerate(fnames):
            C=ReadNC('{}/{}'.format(dir_hycom,fname),1); 
            if m%240==0 or m==len(fnames)-1: print(sname,fname)
            #check data; some abnormal may occurs
            C2=ReadNC('{}/{}'.format(dir_hycom,fname))
            if C2.water_temp.val.min()<0 or C2.water_temp.val.max()>40 or abs(C2.surf_el.val).max()>2 or C2.salinity.val.min()<0 or C2.salinity.val.max()>40:
                print('abnormal value in ',fname,'; will skip this file')
                continue
            ctime=array(C.variables['time'])/24+datenum(2000,1,1); sx=array(C.variables['lon'][:])%360
            sy=array(C.variables['lat'][:]); sz=array(C.variables['depth'][:]); nz=len(sz)
            fpz=lzi>=sz.max(); lzi[fpz]=sz.max()-1e-6
            # update nz
            nz=nz-sum(sz>lzi.max()) #do not use hycom layer that has depth larger than the maximum depth in the model domain
    
            if not array_equal(sx,sx0)*array_equal(sy,sy0)*array_equal(sz,sz0):
                #get interp index for HYCOM data
                if ifix==0:
                    sxi,syi=meshgrid(sx,sy); sxy=c_[sxi.ravel(),syi.ravel()];
                    cvs=array(C.variables['water_temp'][0]); sindns=[]; sindps=[]
                    for ii in arange(nz):
                        print('computing HYCOM interpation index: level={}/{}'.format(ii+1,nz))
                        cv=cvs[ii]; ds=cv.shape; cv=cv.ravel()
                        fpn=abs(cv)>1e3; sindn=nonzero(fpn)[0]; sindr=nonzero(~fpn)[0]; sindp=sindr[near_pts(sxy[sindn],sxy[sindr])]
                        sindns.append(sindn); sindps.append(sindp)
    
                #get interp index for pts
                sx0=sx[:]; sy0=sy[:]; sz0=sz[:]; print('get new interp indices: {}'.format(fname))
                idx=((lxi[:,None]-sx0[None,:])>=0).sum(axis=1)-1; ratx=(lxi-sx0[idx])/(sx0[idx+1]-sx0[idx])
                idy=((lyi[:,None]-sy0[None,:])>=0).sum(axis=1)-1; raty=(lyi-sy0[idy])/(sy0[idy+1]-sy0[idy])
                idz=((lzi[:,None]-sz0[None,:])>=0).sum(axis=1)-1; ratz=(lzi-sz0[idz])/(sz0[idz+1]-sz0[idz])
    
            S.time.extend(ctime)
            for i, cti in enumerate(ctime):
                for k,svari in enumerate(svar):
                    exec("cv=array(C.variables['{}'][{}])".format(svari,i)); mvari=mvar[k]
    
                    #remove HYCOM nan pts
                    if ifix==0:
                        for ii in arange(nz):
                            sindn,sindp=sindns[ii],sindps[ii]
                            cvi=cv[ii].ravel(); fpn=(abs(cvi[sindn])>1e3)*(abs(cvi[sindp])<1e3); cvi[sindn]=cvi[sindp]; fpn=abs(cvi)>1e3 #init fix
                            if sum(fpn)!=0: fni=nonzero(fpn)[0]; fri=nonzero(~fpn)[0]; fpi=fri[near_pts(sxy[fni],sxy[fri])]; cvi[fni]=cvi[fpi] #final fix
                            #fpn=abs(cv[ii].ravel())>1e3; cv[ii].ravel()[fpn]=sp.interpolate.griddata(sxy[~fpn,:],cv[ii].ravel()[~fpn],sxy[fpn,:],'nearest') #old method
    
                    v0=array([cv[idz,idy,idx],cv[idz,idy,idx+1],cv[idz,idy+1,idx],cv[idz,idy+1,idx+1],
                              cv[idz+1,idy,idx],cv[idz+1,idy,idx+1],cv[idz+1,idy+1,idx],cv[idz+1,idy+1,idx+1]])
    
                    #remove nan in parent pts
                    if ifix==1:
                        for ii in arange(8): fpn=abs(v0[ii])>1e3; v0[ii,fpn]=sp.interpolate.griddata(bxyz[~fpn,:],v0[ii,~fpn],bxyz[fpn,:],'nearest',rescale=True)
    
                    v11=v0[0]*(1-ratx)+v0[1]*ratx;  v12=v0[2]*(1-ratx)+v0[3]*ratx; v1=v11*(1-raty)+v12*raty
                    v21=v0[4]*(1-ratx)+v0[5]*ratx;  v22=v0[6]*(1-ratx)+v0[7]*ratx; v2=v21*(1-raty)+v22*raty
                    vi=v1*(1-ratz)+v2*ratz; vi=vi.astype('float32')
    
                    #save data
                    exec('S.{}.append(vi)'.format(mvari))
            C.close();
        S.time=array(S.time); [exec('S.{}=array(S.{})'.format(i,i)) for i in mvar]
    
        #interp in time
        for mvari in mvar:
            exec('vi=S.{}'.format(mvari))
            #svi=interpolate.interp1d(S.time,vi,axis=0)(mtime).astype('float32')
            svi=array([interpolate.interp1d(S.time,vi[:,i])(mtime).astype('float32') for i in arange(vi.shape[1])]).T; vi=None
            if iLP==1: svi=lpfilt(svi,dt,fc).astype('float32') #low-pass
            exec('S.{}=svi'.format(mvari))
        S.time=mtime
    
        #reshape the data, and save
        [exec('S.{}=S.{}.reshape([{},{},{}])'.format(i,i,nt,nobn,nvrt)) for i in mvar]
        exec("vdata=S.{}[...,None].astype('float32')".format(mvar[0]))
        
        if vdata.min()<-10:
            ablay=unique(nonzero(vdata<-10)[2])
            print('value <-10 occurs in layers ',ablay)
            print('manuualy asgin the bottom layer with the value of layer above')
            for ilay in ablay:
                vdata[:,:,ilay,:]=vdata[:,:,ablay[-1]+1,:] #use the layer above the abnormal layers
            if vdata.min()<-10: sys.exit('min value less than -10')
        print(sname,'min and max value: ',vdata.min(),vdata.max())
        #--------------------------------------------------------------------------
        #create netcdf
        #--------------------------------------------------------------------------
        nd=zdata(); nd.file_format='NETCDF4'
    
        #define dimensions
        nd.dimname=['time','node','nLevels','one']
        nd.dims=[nt,nobn,nvrt,1]
    
        #define variables
        nd.vars=['time', 'map_to_global_node', 'tracer_concentration']
        vi=zdata(); vi.dimname=('time',); vi.val=(S.time-S.time[0]); nd.time=vi 
        vi=zdata(); vi.dimname=('node',); vi.val=bind+1; nd.map_to_global_node=vi
        vi=zdata(); vi.dimname=('time','node','nLevels','one'); vi.val=vdata; nd.tracer_concentration=vi
    
        WriteNC(sname,nd)
#%% ===========================================================================
# generating source and sink
#==============================================================================
if 1 in [p.flag[fname] for fname in ['source_sink.in','vsource.th','msource.th']]:
    #==================================================================
    # Inputs
    #==================================================================
    begin_time=p.begin_time; end_time=p.end_time #for model forcing
    flow_dir=p.flow_dir #'../../Observations/usgs_flow/npz/'
    temp_dir=p.temp_dir #'../../Observations/usgs_temp/npz/'
             #river name      #usgs     #lon&lat to model  #flow ratio #temp station                
    rivers={'Alabama River':['02428400',-87.952193,31.114812, 1, 'NOAA8737048'],
            'Tombigbee River':['02469761',-87.952193,31.114812, 1, 'NOAA8737048'], #Merged into Alabama River
            'Pearl River':['02489500',-89.637938,30.286756, 1, 'NOAA8747437'],
            'Mississippi River':['07374000',-91.198213,30.491151, 1, '07374000'], #use usgs
            'Atchafalaya River':['07381490',-91.490298, 30.040207, 1.0,'07381600'], #temp since 2015
            'Calcasieu River':['08015500',-93.283839, 30.199707,1,'NOAA8767961'],
            'Sabine River':['08030500',-93.702267, 30.113907, 1, 'NOAA8770475'], #lacking 2012
            'Neches River':['08041780',-94.087455, 30.103070, 1, 'NOAA8770475'],
            'West Fork Double Bayou':['08042558',-94.662750, 29.708289, 1, '08067252'], #; temp use Wallisville
            'Trinity River':['08067252',-94.744600, 29.876743, 1, '08067252'], #use Wallisville
            'Lost River':['08067252',-94.756050, 29.877047,0.1, '08067252'], #no station, 10% of division is presumed (no ref, should find one)
            'Cedar Bayou':['08067500',-94.919973, 29.778797,1, '08067252'],
            'East Folk Goose Creek':['08067525',-94.980494, 29.751355,1, '08067252'],
            'San Jancinto River':['08072000',-95.130881, 29.918268,0.8, 'NOAA8770777'], #lake houston, water level will be used
            'Greens Bayou':['08076000',-95.224971, 29.813957,1, 'NOAA8770777'], 
            'Buffalo Bayou':['08073600',-95.354827, 29.762263,1,'NOAA8770777'],
            'Brays Bayou':['08075000',-95.332714, 29.714415,1,'NOAA8770777'],
            'Sims Bayou':['08075400',-95.266917, 29.684424,1,'NOAA8770777'],
            'Clear Creek':['08076997',-95.179192, 29.519611,1,'NOAA8771013'], #temp use Eagle Point
            'Dickinson Bayou':['08076997',-95.102342, 29.430227, 1.01,'NOAA8771013'], #no usgs, use clear creek
            'Chocolate Bayou':['08078000',-95.229354, 29.260102,1, 'NOAA8771972'], 
            'Brazos River':['08116650',-95.529603, 29.036087,1, 'NOAA8773146'], #
            'San Bernard River':['08117705',-95.556578, 28.951045,1, 'NOAA8773146'],
            'Caney Creek':['08117705',-95.669999, 28.829155,0.3156, 'NOAA8773146'], #based on watershed compared to San Bernard River
            'Colorado River':['08162501',-96.034883, 28.862348,1, 'NOAA8773146'],
            'Tres Palacios River':['08162600',-96.146563, 28.811765,1, 'NOAA8773146'],
            'Carancahua Creek':['08164000',-96.421990, 28.772334, 0.12, 'NOAA8773146'], #ratio based on Crancahua Creek watershed compared to Lavaca River 
            'Lavaca River':['08164000',-96.576292, 28.869547,1, 'NOAA8773259'],
            'Mission river':['08189500',-97.195667, 28.186161,1, 'NOAA8774770'],
            'Aransas River':['08189700',-97.284350, 28.094783,1, 'NOAA8774770'],
            'Guadalupe River':['08188810',-96.841728, 28.468151,1, 'NOAA8773037'],
            'Saint Antonio River':['08188060',-96.841728, 28.468151,1, 'NOAA8773037'], #merged into Guadalupe
            'Nueces River':['08211200',-97.604969, 27.869262,1,'08211200'], #into CC Bay
            'Petronila Creek':['08212820',-97.525740, 27.523016,1,'NOAA8776604'], #into Baffin Bay
            'San Fernando Creek':['08211900',-97.773413, 27.400734,1,'NOAA8776604'], #into Baffin Bay
            'Los Olmos Creek':['08212400',-97.795990, 27.273561,1,'NOAA8776604']} #into Baffin Bay
    #only rivers in bp.station will be used
    bp=read_schism_bpfile(p.grid_dir+'/rivers.bp')
    bp.station=['Alabama River','Tombigbee River','Mississippi River','Atchafalaya River','Calcasieu River',
                'Sabine River','Neches River','Trinity River','San Jancinto River',  'Buffalo Bayou',
                'Chocolate Bayou', 'Brazos River', 'Colorado River','Guadalupe River','Nueces River', 
                'San Fernando Creek',]
    if len(bp.x) != len(bp.station): sys.exit('rivers.bp is not well prepared')
    tmp={}
    for m,river in enumerate(bp.station):
        tmp[river]=rivers[river]
        tmp[river][1]=bp.x[m]
        tmp[river][2]=bp.y[m]
    rivers=tmp
    #==================================================================
    # gen source_sink.in, find source and sink element near the boundary, check the element depth
    #==================================================================
    if p.flag['source_sink.in']==1:
        print('generate source_sink.in')
        gd=loadz(p.grd).hgrid
        gd.compute_ctr()
        f = open("source_sink.in", "w")
        f.write(f'{len(rivers)} !number of sources\n')
        fps=[]
        for m,river in enumerate(rivers):
            fp=near_pts([rivers[river][1],rivers[river][2]],c_[gd.xctr,gd.yctr])
            f.write(f'{fp+1}  !{m+1} {river} \n')
            fps.append(fp)
        f.write('\n'); f.write('0') #0 for the sink number
        f.close()
        if p.flag['check']==1:
            figure(figsize=[10,6])
            gd.plot_bnd()
            plot(gd.xctr[fps],gd.yctr[fps],'ro')
            savefig('zfig_source_loc.png') 
    #==================================================================
    # gen vsource.th
    #==================================================================
    if p.flag['vsource.th']==1:
        print('writing vsource.th')
        times=arange(begin_time,end_time)
        for m,river in enumerate(rivers):
            if m==0:
                data=(times-begin_time)*86400
            if rivers[river][0] is None: 
                tmp=zeros(len(times))
                data=c_[data,tmp]
                continue
            else:
                sname='{}/{}_2000_2021.npz'.format(flow_dir,rivers[river][0])
                S2=loadz(sname)
            fp=(S2.time>=begin_time)*(S2.time<end_time)
            tmp=S2.flow[fp]*rivers[river][3]
            if sum(fp)!=len(times): sys.exit('dimension error, data length not consistent')
            data=c_[data,tmp]
                    
        fp=data<0
        if sum(fp)>0: print('there is negative flow; zero value will be used')
        data[data<0]=0
        with open('vsource.th','w') as f:
            mat = np.matrix(data)
            for line in mat:
                np.savetxt(f, line, fmt='%.2f')
    
    #==================================================================
    # gen msource.th  get temperature from USGS and noaa
    #==================================================================
    if p.flag['msource.th']==1:
        for m,river in enumerate(rivers):
            if m==0:
                data=(times-begin_time)*86400
            if rivers[river][4] is None: 
                tmp=zeros(len(times))
                data=c_[data,tmp]
                continue
            else:
                sname='{}/{}_2000_2021.npz'.format(temp_dir,rivers[river][4].replace('NOAA',''))
                S2=loadz(sname)
            fp=(S2.time>=begin_time)*(S2.time<end_time)
            tmp=S2.temp[fp]
            if sum(fp)!=len(times): sys.exit('dimension error, data length not consistent')
            data=c_[data,tmp]
        
        data=c_[data,0*data[:,1:]] #add salinity
        print('generate msource.in')
        with open('msource.th','w') as f:
            mat = np.matrix(data)
            for line in mat:
                np.savetxt(f, line, fmt='%.2f')

#%% ==========================================================================
# generating sflux files by linking to existing sflux files
#=============================================================================
if p.flag['sflux']==1:
   print('writing sflux')
   #parameters
   tdir='./sflux'      #target dir
   itag=1              #itag=[1 or 2],for sflux_air_itag.0691.nc 
   
   #make links
   bdir=os.path.abspath(os.path.curdir); tdir=os.path.abspath(tdir)
   if fexist(tdir): os.system('rm -rf {}'.format(tdir))
   os.mkdir(tdir); os.chdir(tdir)
   mtime=arange(p.begin_time,p.end_time+1); svars=['air','rad','prc']
   for irec,ti in enumerate(mtime):
       #link each file
       year=num2date(ti).year; month=num2date(ti).month; day=num2date(ti).day
       for m,svar in enumerate(svars):
           fname='{}/sflux_{}.{:04d}_{:02d}_{:02d}.nc'.format(p.sflux,svar,year,month,day)
           os.symlink(os.path.relpath(fname),'sflux_{}_{}.{:04d}.nc'.format(svar,itag,irec+1))
           if m==1 and month==1 and day==1: print('    sflux: {:04d}-{:02d}-{:02d}'.format(year,month,day))
   #write sflux_inputs.txt
   fid=open('{}/sflux_inputs.txt'.format(tdir),'w+'); fid.write('&sflux_inputs\n   \n/'); fid.close()
   os.chdir(bdir)

#%% ==========================================================================
# checking generated forcing files
#=============================================================================
if p.flag['check']==1:
    pass

#%% ==========================================================================
# xxx 
#=============================================================================
if p.flag['run']==1:
    tmp=os.getcwd().split('/')
    run=tmp[-1]
    if os.path.exists(f'../../{run}'): os.system(f'rm -rf ../../{run}')
    os.mkdir(f'../../{run}')
    cmd=f'cd ../{p.setup_dir}; cp param.nml run.sciclone run.frontera mkoutput.py ../../{run}'
    print(cmd); os.system(cmd)
    cmd=f'cd ../../{run}; ./mkoutput.py; ln -sf ../Inputs/{run}/* .; rm zfig*.png'
    print(cmd); os.system(cmd)

