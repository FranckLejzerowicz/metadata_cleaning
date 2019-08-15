#!/usr/bin/env python3
# ----------------------------------------------------------------------------
# Copyright (c) 2019--, Clean development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------

import pandas as pd
import re


def set_column_dtypes(dtypes, column, float_to_string):
    """
    Fill the dtypes object with the temporary dtype inferred from the data
    """
    # add temporary inferred dtype of the column
    if not float_to_string[2]:
        #  if there is no non-float in the column
        # (note the column could be only np.nan, which are floats!)
        dtypes[column].append('float64')
    elif float_to_string[2]:
        # if there is at least one non-float
        if float_to_string[1] or float_to_string[0]:
            # but also a float --> flag to further check
            dtypes[column].append('check')
        else:
            # only non-floats
            dtypes[column].append('object')
    return dtypes


def get_dtypes_and_unks(pd_tab, regex_unk, sampleID_cols=None):
    """
    Get the native dtype and infer it too for each column of the passed metadata.
    Also get the the unknown factors that are ultimately considered "missing"
        metadata. Are considered as such: "short" string (<30 chars)
        containing none of ['/', '-', ':'] and no digit at all


    Parameters
    ----------
    pd_tab : pd.DataFrame
        Metadata table in pandas (columns = variable, rows = observations).

    Returns
    -------
    dtypes : dict
        keys    -> metadata columns
        values  -> 2-items lists
            [0] native dtype (from the pd.Series of columns)
            [1] inferred dtype ('object', 'float64' or 'check')

    potential_unks : dict
        keys    -> "NaN" metadata factor (e.g. "not provided")
        values  -> n-items lists
            [...] metadata columns where "NaN" factor is encountered

    nan_diversity: set
        all possible factors of all metadata variables that hit the
        regex used to identify potentially "NaN" / "missing" data

    """
    if sampleID_cols:
        sampleIDs = sampleID_cols
    else:
        sampleIDs = ['#SampleID', 'sample_name']

    dtypes = {}
    potential_unks = {}
    nan_diversity = set()
    for column in pd_tab.columns:
        native_dtype = str(pd_tab[column].dtypes)  # get native dtype (may be "wrong")
        dtypes[column] = [native_dtype]
        float_to_string = [0, 0, 0, []]
        #  [0] - int  : contains a 'nan'
        #  [1] - int  : contains a 'float64'
        #  [2] - int  : contains a non-'float64'
        #  [3] - list : collect the unique non-'float64's
        if column in sampleIDs:
            # force "#SampleID" or "sample_name" to not be a string
            dtypes[column].append('object')
            continue
        # look at content non "sample identifier" columns
        for V in pd_tab[column].unique():
            v = str(V).lower()
            if re.search(regex_unk, v):
                if ':Unspecified' not in V:
                    nan_diversity.add(V)
            if str(V) == 'nan':
                float_to_string[0] += 1
            else:
                # check if column contains at least one float
                try:
                    float_V = float(V)
                    float_to_string[1] += 1
                except:
                    float_to_string[2] += 1
                    float_to_string[3].append(V)
                    if len(v) < 20 and '/' not in v and '-' not in v and not len([x for x in str(v) if x.isdigit()]):
                        potential_unks.setdefault(v, []).append(column)
        dtypes = set_column_dtypes(dtypes, column, float_to_string)
    return dtypes, potential_unks, nan_diversity


def get_certainly_NaNs(potential_unks, md_pd, thresh=10):
    """
    Count the occurrences of the potential NaN (et al.)
    variables factors and return those that more than a
    given number of times.

    Parameters
    ----------
    potential_unks : dict
        all the factors that have the characetristics of a NaN.

    md_pd : pd.DataFrame
        original metadata table.

    thresh : int
        minimun number of occurrences across the entire dataset
        to be considered a recurrent NaN and then to be staged
        for replacement.

    Returns
    -------
    certainly_NaNs : ps.Series
        final list of sufficiently occurrent factors that may be
        check by user and set on stage for replacement by commmon
        NaN-encoding value.
    """
    # encode the entire metadata as binary for each potential missing factor
    potential_unks_pd_L = []
    for col in md_pd.columns:
        potential_unks_pd_L.append(
            [1 if col in unk_samples else 0 for unk, unk_samples in sorted(potential_unks.items())])

    # make this binary data a dataframe
    potential_unks_pd = pd.DataFrame(potential_unks_pd_L,
                                     index=md_pd.columns.tolist(),
                                     columns=sorted(potential_unks.keys()))
    nrows = potential_unks_pd.shape[0]
    sumCols = potential_unks_pd.sum(0)

    # Keep only the columns (i.e. the variables) that have at least 10 entries
    # all_unks_pd_common = all_unks_pd.loc[:, sumCols > (nrows*0.1)]
    certainly_NaNs = potential_unks_pd.loc[:, sumCols > thresh]
    return certainly_NaNs


def get_dtypes_final(dtypes, md_pd, sampleID_cols):
    """
    Verify the dtypes of each column and apply
    it to some of the metadata columns.

    Parameters
    ----------
    dtypes : dict
        dtypes inferred from the metadata.
        e.g. {'sample_name': 'O', ...
              'age_years': 'Q'}

    md_pd : pd.DataFrame
        original metadata table.

    Returns
    -------
    dtypes_final : dict
        final dtypes verified for NaN columns that me current
        hybrids between 'nan' as "object" and float64.

    md_pd : pd.DataFrame
        final metadata table with updated dtypes for the
        columns that have inconsistent dtypes based on inference.
    """
    if sampleID_cols:
        sampleIDs = sampleID_cols
    else:
        sampleIDs = ['#SampleID', 'sample_name']
    dtypes_final = {}
    for col, checks in dtypes.items():

        if col in sampleIDs:
            dtypes[col].append('object')
            dtypes_final[col] = 'O'
        elif checks[-1] in ['check', 'object']:
            md_pd = md_pd.replace({col: to_nan})
            for v in md_pd[col].unique():
                if str(v) == 'nan':
                    continue
                else:
                    try:
                        float_v = float(v)
                        continue
                    except:
                        dtypes[col].append('object')
                        dtypes_final[col] = 'O'
                        break
            else:
                dtypes[col].append('float64')
                dtypes_final[col] = 'Q'
        else:
            dtypes[col].append(checks[-1])
            dtypes_final[col] = 'Q'
    return dtypes_final, md_pd


def rectify_dtypes_in_md(dtypes_final, md_pd):
    """
    Fetch the freshly identified dtypes of each column
    and apply it to the main metadata.

    Parameters
    ----------
    dtypes_final : dict
        dtypes inferred from the metadata and verified
        e.g. {'sample_name': 'O',
              ...
              'age_years': 'Q'}

    md_pd : pd.DataFrame
        original metadata table

    Returns
    -------
    md_pd : pd.DataFrame
        final metadata table with updated dtypes
    """
    for col, dtype in dtypes_final.items():
        if col in md_pd.columns.tolist():
            if dtype == 'Q':
                md_pd[col] = md_pd[col].astype('float64')
            else:
                md_pd[col] = md_pd[col].astype('str')
        else:
            md_pd[col] = md_pd[col].astype('str')
    return md_pd
