# %%

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


df = pd.read_pickle("C:\\Users\\TeraSmart-PC\\Documents\\TheaPython\\TQC\\Analysis\\DFs\\90-90-360_proper1CA.pkl")

fLim = df.loc[0]['freq'][900]  # 1.6 THz
ang = np.linspace(90,-90,360)

df["phi"] = ang

# %%
imrows = []
phis = []
for i in range(len(df)):
    imrows.append(20*np.log(abs(df.loc[i]['FFT'][:900])))  # only take spectra till 3.479 THz
    phis.append(df.loc[i]['phi'])
imrows = np.array(imrows)

cmaps = ['Accent', 'Accent_r', 'Blues', 'Blues_r', 'BrBG', 'BrBG_r', 'BuGn',
         'BuGn_r', 'BuPu', 'BuPu_r', 'CMRmap', 'CMRmap_r', 'Dark2', 'Dark2_r', 
         'GnBu', 'GnBu_r', 'Greens', 'Greens_r', 'Greys', 'Greys_r', 'OrRd', 
         'OrRd_r', 'Oranges', 'Oranges_r', 'PRGn', 'PRGn_r', 'Paired', 'Paired_r', 
         'Pastel1', 'Pastel1_r', 'Pastel2', 'Pastel2_r', 'PiYG', 'PiYG_r', 'PuBu', 
         'PuBuGn', 'PuBuGn_r', 'PuBu_r', 'PuOr', 'PuOr_r', 'PuRd', 'PuRd_r', 'Purples', 
         'Purples_r', 'RdBu', 'RdBu_r', 'RdGy', 'RdGy_r', 'RdPu', 'RdPu_r', 'RdYlBu', 
         'RdYlBu_r', 'RdYlGn', 'RdYlGn_r', 'Reds', 'Reds_r', 'Set1', 'Set1_r', 'Set2', 
         'Set2_r', 'Set3', 'Set3_r', 'Spectral', 'Spectral_r', 'Wistia', 'Wistia_r', 
         'YlGn', 'YlGnBu', 'YlGnBu_r', 'YlGn_r', 'YlOrBr', 'YlOrBr_r', 'YlOrRd', 
         'YlOrRd_r', 'afmhot', 'afmhot_r', 'autumn', 'autumn_r', 'binary', 
         'binary_r', 'bone', 'bone_r', 'brg', 'brg_r', 'bwr', 'bwr_r', 
         'cividis', 'cividis_r', 'cool', 'cool_r', 'coolwarm', 'coolwarm_r', 
         'copper', 'copper_r', 'cubehelix', 'cubehelix_r', 'flag', 'flag_r', 
         'gist_earth', 'gist_earth_r', 'gist_gray', 'gist_gray_r', 'gist_heat', 
         'gist_heat_r', 'gist_ncar', 'gist_ncar_r', 'gist_rainbow', 'gist_rainbow_r', 
         'gist_stern', 'gist_stern_r', 'gist_yarg', 'gist_yarg_r', 'gnuplot',
         'gnuplot2', 'gnuplot2_r', 'gnuplot_r', 'gray', 'gray_r', 'hot', 'hot_r', 
         'hsv', 'hsv_r', 'inferno', 'inferno_r', 'jet', 'jet_r', 'magma', 'magma_r', 
         'nipy_spectral', 'nipy_spectral_r', 'ocean', 'ocean_r', 'pink', 'pink_r', 
         'plasma', 'plasma_r', 'prism', 'prism_r', 'rainbow', 'rainbow_r', 'seismic', 
         'seismic_r', 'spring', 'spring_r', 'summer', 'summer_r', 'tab10', 'tab10_r', 
         'tab20', 'tab20_r', 'tab20b', 'tab20b_r', 'tab20c', 'tab20c_r', 'terrain', 'terrain_r', 
         'turbo', 'turbo_r', 'twilight', 'twilight_r', 'twilight_shifted', 'twilight_shifted_r', 
         'viridis', 'viridis_r', 'winter', 'winter_r']

# %%

fig, ax = plt.subplots(figsize=(6,6))
phiScan = ax.imshow(imrows, cmap= 'afmhot_r', vmin =-180 , vmax = -110,extent =[df.loc[0]['freq'][0],fLim,phis[0],phis[-1]])
ax.set_aspect(0.015)
ax.set_xlabel("Frequency (THz)")
ax.set_ylabel("Phi (deg)")

cbar = fig.colorbar(phiScan, ax = ax, location = 'right', fraction=0.046, pad=0.04)

cbar.set_label("Transmission (arb dB)")
plt.show()