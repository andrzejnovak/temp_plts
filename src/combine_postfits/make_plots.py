import os
import numpy as np
import uproot
import logging
import yaml
import json
import matplotlib
from multiprocessing import Process, Semaphore
import time
import fnmatch
import importlib.util

matplotlib.use("Agg")
import mplhep as hep
import argparse

from combine_postfits import plot, utils

import click
from rich.logging import RichHandler
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
    SpinnerColumn
)
from rich.prompt import Confirm
from rich.traceback import install
install(show_locals=False)

ROOT_spec = importlib.util.find_spec("ROOT")
ROOT_AVAILABLE = ROOT_spec is not None
if ROOT_AVAILABLE:
    import ROOT as r

hep.style.use("CMS")


def time_check(progress, procs, limit=5):
    if progress.tasks[0].elapsed//60 >= limit:
        logging.error(f"Plotting taking longer than {limit} minutes. Likely and issue with file opening or too many figures. Try rerunning or running with `--p 0`.")
        remaining_procs = [p for p in procs if p.is_alive()]
        logging.error(f"Terminating remaining plot processes: {[p.name for p in remaining_procs]}")
        for p in remaining_procs:
            p.terminate()
        import sys
        sys.exit()


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def sci_notation(number, sig_fig=1, no_zero=False):
    ret_string = "{0:.{1:d}e}".format(number, sig_fig)
    a, b = ret_string.split("e")
    b = int(b)
    if float(a) == 0:
        if no_zero:
            return "\ "
        else:
            return "0"
    elif float(a) == 1:
        return "10^{" + str(b) + "}"
    else:
        return a + "\,x\," + "10^{" + str(b) + "}"


def get_digits(number):
    before, _, after = np.round(number, 10).astype(str).partition(".")
    return len(before), len(after)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i", "--input", default="fitDiagnosticsTest.root", help="Input shapes file"
    )
    parser.add_argument(
        "--fit",
        default="all",
        choices={"prefit", "fit_s", "fit_b",    "all"},
        dest="fit",
        help="Shapes to plot",
    )
    parser.add_argument(
        "-o",
        "--output-folder",
        default="plots",
        dest="output_folder",
        help="Folder to store plots - will be created if it doesn't exist.",
    )
    parser.add_argument(
        "--cats",
        default=None,
        dest="cats",
        help="Either a comma-separated list of categories to plot or a mapping of categories to plot together, e.g. `cat1,cat2` in the form of `mcat1:cat1,cat2;mcat2:cat3,cat4`",
    )
    parser.add_argument(
        "--sigs",
        default=None,
        dest="sigs",
        help="Comma-separated list of keys available in provided `--style sty.yml` file, e.g. `ggH,VBF`",
    )
    parser.add_argument(
        "--project-signals",
        "--project_signals",
        default=None,
        dest="project_signals",
        help="Comma-separated list of values of equal length with --sigs, e.g. `1,1`.",
    )
    parser.add_argument(
        "--bkgs",
        default=None,
        dest="bkgs",
        help="Comma-separated list of keys available in provided `--style sty.yml` file, e.g. `ggH,VBF`",
    )
    parser.add_argument(
        "--rmap",
        default=None,
        dest="rmap",
        # type=json.loads,
        help="A dict-like string e.g. `hbb:r_q,htt:r_t`",
    )
    parser.add_argument(
        "--onto",
        default=None,
        dest="onto",
        help="Bkg to plot other processes onto, e.g. `qcd`.",
    )
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        default="png",
        choices={"png", "pdf", "both"},
        help="Plot format",
    )
    # Styling/Colors
    parser.add_argument(
        "-s",
        "--style",
        default=None,
        dest="style",
        help="Style file yaml e.g. `style.yml`",
    )
    parser.add_argument(
        "--cmap",
        type=str,
        default=None,
        help="Name of `cmap` to fill colors in `style.yml` from. Eg.: Tiepolo;Renoir;tab10",
    )
    parser.add_argument(
        "--clipx",
        type=str2bool,
        default="True",
        choices={True, False},
        help="Clip x-axis to range of data",
    )

    # Labels
    pseudo = parser.add_mutually_exclusive_group(required=True)
    pseudo.add_argument("--data", action="store_false", dest="pseudo")
    pseudo.add_argument("--MC", action="store_true", dest="pseudo")
    pseudo.add_argument("--toys", action="store_true", dest="toys")
    parser.add_argument(
        "--blind",
        type=str,
        default=None,
        help="Category to blind data (not plotted), e.g. `cat1`",
    )
    parser.add_argument("--unblind", action="store_true", dest="unblind")
    parser.add_argument(
        "--year",
        default=None,
        choices={"2016", "2017", "2018", ""},
        type=str,
        help="year label",
    )
    parser.add_argument(
        "--lumi",
        default=None,
        type=float,
        help="Luminosity for label",
    )
    parser.add_argument(
        "--pub",
        default=None,
        type=str,
        help="arxiv no",
    )
    parser.add_argument(
        "--xlabel",
        default=None,
        type=str,
        help="Plot x-label eg `$m_{\tau\bar{\tau}}^{reg}$`. If left `None` will read from combine. When using latex enclose string as 'str'.",
    )
    parser.add_argument(
        "--ylabel",
        default=None,
        type=str,
        help="Plot y-label. If left `None` will read from combine. When using latex enclose string as 'str'.",
    )
    parser.add_argument(
        "--no_zero",
        type=str2bool,
        default="False",
        choices={True, False},
        help="Hide zeroth tick on the y-axis.",
    )
    parser.add_argument(
        "--chi2",
        type=str2bool,
        default="True",
        choices={True, False},
        help="Don't show chi2 indicator",
    )
    parser.add_argument(
        "--cmslabel",
        default="Private Work",
        type=str,
        help="CMS Label",
    )
    parser.add_argument(
        "--catlabels",
        default=None,
        type=str,
        help="Category label to replace automated labelling. To pass per-category label, use `;` separator.",
    )
    parser.add_argument(
        "--dpi",
        default=300,
        type=int,
        help="dpi for png format",
    )
    parser.add_argument("--noroot", action="store_true", help="Skip ROOT dependency")

    # Debug
    parser.add_argument("--verbose", "-v", "-_v", action="store_true", help="Verbose logging")
    parser.add_argument("--debug", "-vv", "--vv", action="store_true", help="Debug logging")
    parser.add_argument(
        "-p",
        nargs='?', 
        default=0, 
        const=10,
        type=int,
        dest="multiprocessing",
        help="Use multiprocessing to make plots. May fail due to parallel reads from fitDiag. `-p` defaults to 10 processes.",
    )
    args = parser.parse_args()

    os.makedirs(args.output_folder, exist_ok=True)

    # Arg processing
    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, tracebacks_suppress=[click])],
    )
    if not args.pseudo and not args.unblind:
        unblind_conf = Confirm.ask(
            "Option `--blind` is not set, while plotting with `--data`. "
            "Hi Eric, are you sure you want to unblind? (pass `--unblind` to suppress this prompt)"
        )
        assert unblind_conf, "Unblind option not confirmed. Exiting."

    if args.fit == "all":
        fit_types = ["prefit", "fit_s"]
    else:
        fit_types = [args.fit]
    for fit in fit_types:
        os.makedirs(f"{args.output_folder}/{fit}", exist_ok=True)
    if args.format == "both":
        format = ["png", "pdf"]
    else:
        format = [args.format]

    # Make plots
    fd = uproot.open(args.input)
    if ROOT_AVAILABLE and not args.noroot:
        rfd = r.TFile.Open(args.input)
    else:
        rfd = None
    if args.style is not None:
        with open(args.style, "r") as stream:
            style = yaml.safe_load(stream)
    else:
        style = utils.make_style_dict_yaml(fd, cmap=args.cmap, sort=True, sort_peaky=True)
        logging.warning(
            "No `--style sty.yml` file provided, will generate an automatic style yaml and store it as `sty.yml`. "
            "The `plot` function will respect the order of samples in the style yaml unless overwritten. "
            "\nTo pass LaTeX expressions to 'label' use single quotes eg. '$H_{125}(\\tau\\bar{\\tau})$'"
        )
        with open("sty.yml", "w") as outfile:
            yaml.dump(style, outfile, default_flow_style=False, sort_keys=False)

    if args.pseudo and args.toys:
        style["data"]["label"] = "Toys"
    elif args.pseudo and not args.toys:
        style["data"]["label"] = "MC"
    else:
        style["data"]["label"] = "Data"

    if args.blind is not None:
        blind_cats = args.blind.split(",") if "," in args.blind else [args.blind]
    else:
        blind_cats = []

    # Parse rmap
    if args.rmap is not None:
        kvs = args.rmap.split(",")
        rmap = {kv.split(":")[0]: kv.split(":")[1] for kv in kvs}

    else:
        rmap = None
    if args.sigs is not None:
        _unset_sigs = [sig for sig in args.sigs.split(",") if rmap is None or sig not in rmap]
        if len(_unset_sigs) > 0:
            logging.warning(f"Signals '{','.join(_unset_sigs)}' not found in rmap: `{rmap}`. To display signal strengths pass `--rmap '{','.join([f'{_sig}:r_param' for _sig in _unset_sigs])}'`.")

    # Get types/cats/blinds unwrapped
    all_channels = []
    all_blinds = []
    all_types = []
    all_savenames = []
    all_labels = []
    for fit_type in fit_types:
        # all channels
        available_channels = [
                c[:-2] for c in fd[f"shapes_{fit_type}"].keys() if c.count("/") == 0
        ]
        logging.debug(f"Available '{fit_type}' channels: {available_channels}")
        # Take all unless blinded
        if args.cats is None:
            channels = [[c] for c in available_channels]
            blinds = [True if c[0] in blind_cats else False for c in channels]
            savenames = [c for c in available_channels]
            labels = [None for c in available_channels]
            logging.debug(f"Plotting channels: {channels}")
        # Parse --cats, either mapping or list
        else:
            # mapping
            if ":" in args.cats:
                channels = []
                blinds = []
                savenames = []
                for cat in args.cats.split(";"):
                    mcat, cats = cat.split(":")
                    cats = sum([fnmatch.filter(available_channels, _cat) for _cat in cats.split(",")], [])
                    # channels.append(cats.split(","))
                    channels.append(cats)
                    blinds.append(True if mcat in blind_cats else False)
                    savenames.append(mcat)
                    logging.debug(f"Plotting merged channels '{mcat}': {cats}")
            # list
            else:
                channels = sum([fnmatch.filter(available_channels, _cat) for _cat in args.cats.split(",")], [])
                blinds = [
                    True if c in blind_cats else False for c in channels
                ]
                savenames = [c for c in channels]
                channels = [[c] for c in channels]
                logging.debug(f"Plotting channels: {channels}")
            if args.catlabels is not None:
                if ";" in args.catlabels:
                    labels = args.catlabels.split(";")
                else:
                    labels = [args.catlabels for c in channels]
            else:
                labels = [c for c in savenames]
            labels = ["\n".join(lab.split("\\n")) for lab in labels]  # hacky but needed to pass \n from cmdline
        assert len(channels) != 0, f"Channel matching failed for --cats '{args.cats}'. Available categories are :{available_channels}"
        assert isinstance(channels[0], list)
        all_channels.extend(channels)
        all_blinds.extend(blinds)
        all_types.extend([fit_type] * len(channels))
        all_savenames.extend(savenames)
        all_labels.extend(labels)
    logging.debug(f"All Channels: {all_channels}")
    logging.debug(f"All Blinds: {all_blinds}")
    logging.debug(f"All Types: {all_types}")
    logging.debug(f"All Savenames: {all_savenames}")
    logging.debug(f"All Labels: {all_labels}")

    _procs = []
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        SpinnerColumn(),
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
    ) as progress:
        prog_str_fmt = (
            "[red]Plotting ({} workers): " if args.multiprocessing > 0 else "[red]Plotting: "
        )
        prog_str = prog_str_fmt.format("N")
        prog_plotting = progress.add_task(prog_str, total=len(all_channels))
        semaphore = Semaphore(args.multiprocessing)
        for fittype, channel, blind, sname, label in zip(
            all_types, all_channels, all_blinds, all_savenames, all_labels
        ):
            # Wrap it in a function to enable parallel processing
            if label is None:
                label = 1 if len(channel) < 6 else {s.split(":")[0]:s.split(":")[1] for s in args.cats.split(";")}[sname]
            def mod_plot(semaphore=None):
                fig, (ax, rax) = plot.plot(
                    fd,
                    fittype,
                    sigs=args.sigs.split(",") if args.sigs else None,
                    bkgs=args.bkgs.split(",") if args.bkgs else None,
                    onto=args.onto,
                    project_signal=[float(v) for v in args.project_signals.split(",")]
                    if args.project_signals
                    else None,
                    rmap=rmap,
                    blind=blind,
                    cats=channel,
                    restoreNorm=True,
                    clipx=args.clipx,
                    fitDiag_root=rfd,
                    style=style,
                    cat_info=label,
                    chi2=args.chi2,
                )
                if fig is None:
                    return None
                # Styling
                if args.xlabel is not None:
                    rax.set_xlabel(args.xlabel)
                if args.ylabel is not None:
                    ax.set_ylabel(args.ylabel)
                hep.cms.label(
                    args.cmslabel,
                    data=not args.pseudo,
                    ax=ax,
                    lumi=args.lumi,
                    lumi_format="{:0.0f}",
                    pub=args.pub,
                    year=args.year,
                )
                # ax.semilogy()
                # ax.set_ylim(10, None)

                # Sci notat
                leading_dig_max, decimal_dig_max = 0, 0
                for tick in ax.get_yticks():
                    leading_dig_max = max(leading_dig_max, get_digits(tick)[0])
                    decimal_dig_max = max(decimal_dig_max, get_digits(tick)[1])
                if (leading_dig_max > 3) or (decimal_dig_max > 3):

                    def g(x, pos):
                        return rf"${sci_notation(x, sig_fig=1, no_zero=args.no_zero)}$"

                    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(g))

                # Save
                for fmt in format:
                    logging.debug(f"Saving: '{args.output_folder}/{fittype}/{sname}_{fittype}.{fmt}'")
                    fig.savefig(
                        f"{args.output_folder}/{fittype}/{sname}_{fittype}.{fmt}",
                        format=fmt,
                        dpi=args.dpi,
                        bbox_inches="tight",
                        # transparent=True,
                    )
                if semaphore is not None:
                    semaphore.release()

            if args.multiprocessing > 0:
                semaphore.acquire()
                p = Process(target=mod_plot, args=(semaphore,), name=sname)
                _procs.append(p)
                p.start()
                time.sleep(0.1)
                
                n_running = sum([p.is_alive() for p in _procs])
                progress.update(
                    prog_plotting, completed=len(_procs) - n_running, refresh=True, description=prog_str_fmt.format(n_running),
                )
                time_check(progress, _procs, 6)
            else:
                mod_plot()
                progress.update(prog_plotting, advance=1, refresh=True)
        if args.multiprocessing > 0:
            while sum([p.is_alive() for p in _procs]) > 0:
                n_running = sum([p.is_alive() for p in _procs])
                progress.update(
                    prog_plotting, completed=len(_procs) - n_running, refresh=True, description=prog_str_fmt.format(n_running),
                )
                time.sleep(0.1)
                
                time_check(progress, _procs, 6)
        progress.update(prog_plotting, completed=len(all_channels), total=len(all_channels), refresh=True, description=prog_str_fmt.format(0))


if __name__ == "__main__":
    main()
