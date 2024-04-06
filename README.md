### Installation

```
gh repo clone andrzejnovak/combine_postfits
cd combine_postfits
pip install -e .
```

### Run

Example script to be modified as needed can be found in `make_plots.py. Run as:

```
 python make_plots.py -i hadelModel_m125/fitDiagnosticsTest.root -v --MC --style style_jeff.yml
```

If you install the non-editable version `pip install .` You can access it as `combine_postfits `

```
usage: combine_postfits [-h] [-i INPUT] [--fit {fit_s,prefit,all}] [-o OUTPUT_FOLDER] [--cats CATS] [--sigs SIGS] [--project-signals PROJECT_SIGNALS] [--bkgs BKGS] [--onto ONTO] [-f {both,png,pdf}] [-s STYLE] [--cmap CMAP] [--clipx {False,True}] (--data | --MC | --toys)
                        [--blind BLIND] [--year {,2018,2017,2016}] [--lumi LUMI] [--pub PUB] [--xlabel XLABEL] [--ylabel YLABEL] [--cmslabel CMSLABEL] [--verbose] [--debug] [-p]

options:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input shapes file
  --fit {fit_s,prefit,all}
                        Shapes to plot
  -o OUTPUT_FOLDER, --output-folder OUTPUT_FOLDER
                        Folder to store plots - will be created if it doesn't exist.
  --cats CATS           Either a comma-separated list of categories to plot or a mapping of categories to plot together, e.g. `cat1,cat2` in the form of `mcat1:cat1,cat2;mcat2:cat3,cat4`
  --sigs SIGS           Comma-separated list of keys available in provided `--style sty.yml` file, e.g. `ggH,VBF`
  --project-signals PROJECT_SIGNALS, --project_signals PROJECT_SIGNALS
                        Comma-separated list of values of equal length with --sigs, e.g. `1,1`
  --bkgs BKGS           Comma-separated list of keys available in provided `--style sty.yml` file, e.g. `ggH,VBF`
  --onto ONTO           Bkg to plot other processes onto, e.g. `qcd`.
  -f {both,png,pdf}, --format {both,png,pdf}
                        Plot format
  -s STYLE, --style STYLE
                        Style file yaml e.g. `style.yml`
  --cmap CMAP           Name of `cmap` to fill colors in `style.yml` from. Eg.: Tiepolo;Renoir;tab10
  --clipx {False,True}  Clip x-axis to range of data
  --data
  --MC
  --toys
  --blind BLIND         Category to blind data (not plotted), e.g. `cat1`
  --year {,2018,2017,2016}
                        year label
  --lumi LUMI           Luminosity for label
  --pub PUB             arxiv no
  --xlabel XLABEL       Plot x-label. If left `None` will read from combine. When using latex enclose string as 'str'.
  --ylabel YLABEL       Plot y-label. If left `None` will read from combine. When using latex enclose string as 'str'.
  --cmslabel CMSLABEL   CMS Label
  --verbose, -v         Verbose logging
  --debug, -vv          Debug logging
  -p                    Use multiprocessing to make plots. May fail due to parallel reads from fitDiag.
  ```



  ### Examples

  Tests
   - style/no style
   - scaled sigs
   - no cats, list cats, map cats, both with wildcards


  ### Examples


- `fit_diag_A.root`
  - Simple
  ```
  combine_postfits -i fitDiags/fit_diag_A.root -o outs/plots_A_all --data --unblind  -p
  ```

  - Customized
  ```
  combine_postfits -i fitDiags/fit_diag_A.root -o outs/plots_A --style styles/style_A.yml --data --unblind --sigs hcc,zcc --onto qcd --rmap zcc:z,hcc:r  --cats 'pass:ptbin*pass2016;fail:ptbin*fail*;muCRpass:muonCRpass2016;muCRfail:muonCRfail2016' --bkgs top,other,wqq,wcq,zqq,zbb,hbb -vv --project-signal 200,0 -p
  ```

- `fit_diag_Abig.root`
  - Simple
  ```
  combine_postfits -i fitDiags/fit_diag_Abig.root -o outs/plots_Abig_all --data --unblind  -p
  ```

  - Customized
  ```
  combine_postfits -i fitDiags/fit_diag_Abig.root -o outs/plots_Abig --style styles/style_A.yml --data --unblind --sigs hcc,zcc --onto qcd --rmap zcc:z,hcc:r  --cats 'pass16:ptbin*pass2016;fail16:ptbin*fail2016;pass17:ptbin*pass2017;fail17:ptbin*fail2017;pass18:ptbin*pass2018;fail18:ptbin*fail2018;pass:ptbin*pass*;fail:ptbin*fail*;muCRpass16:muonCRpass2016;muCRfail16:muonCRfail2016;muCRpass17:muonCRpass2017;muCRfail17:muonCRfail2017;muCRpass18:muonCRpass2018;muCRfail18:muonCRfail2018' --bkgs top,other,wqq,wcq,zqq,zbb,hbb -vv --project-signal 200,0 -p
  ```
  
- `fit_diag_D.root`
  - Simple
  ```
  combine_postfits -i fitDiags/fit_diag_D.root -o outs/plots_D_all --MC  -p
  ```

  - Customized
  ```
  combine_postfits -i fitDiags/fit_diag_D.root -o outs/plots_D --MC --style styles/style_D.yml --onto qcd --sigs VH --bkgs qcd,top,Wjets,Zjets,VV,H  --rmap 'VH:rVH' --project-signals 3 --xlabel 'Jet $m_{SD}$' -p
  ```