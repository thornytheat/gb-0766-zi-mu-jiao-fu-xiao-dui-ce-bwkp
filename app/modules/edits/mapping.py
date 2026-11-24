from bisect import bisect_right
from fractions import Fraction
from math import ceil
from app.modules.clock.timecode import RATIO
from app.rational import show


def map_cues(cues, edit_list):
    main = [edit for edit in edit_list if edit['kind'] != 'RECAP']
    recaps = [edit for edit in edit_list if edit['kind'] == 'RECAP']
    endpoints = [edit['end'] for edit in main]
    recap_ends = [edit['end'] for edit in recaps]
    fragments = []
    for cue in cues:
        start, end = Fraction(cue['start']), Fraction(cue['end'])
        cursor = start
        for edit in main[bisect_right(endpoints, cursor):]:
            if edit['start'] >= end:
                break
            left, right = max(cursor, edit['start']), min(end, edit['end'])
            if cursor < left:
                fragments.append(fragment(cue, cursor, left, None))
            fragments.append(fragment(cue, left, right, edit))
            cursor = right
        if cursor < end:
            fragments.append(fragment(cue, cursor, end, None))
        for edit in recaps[bisect_right(recap_ends, start):]:
            if edit['start'] >= end:
                break
            fragments.append(fragment(cue, max(start, edit['start']), min(end, edit['end']), edit))
    return dict(rows=fragments, cuts=edit_list, recaps=recap_pairs(fragments, edit_list),
                counts={kind: sum(row['kind'] == kind for row in fragments)
                        for kind in ('KEEP', 'REMOVE', 'RECAP', 'GAP')})


def fragment(cue, start, end, edit):
    kind = edit['kind'] if edit else 'GAP'
    result = dict(cue_id=cue['cue_id'], track=cue['track'], line=cue['line'], text=cue['text'],
                  start=show(start), end=show(end), kind=kind, cut=edit['cut'] if edit else None,
                  cut_line=edit['line'] if edit else None)
    if kind in ('KEEP', 'RECAP'):
        left = edit['target'] + (start - edit['start']) * RATIO
        right = edit['target'] + (end - edit['start']) * RATIO
        result.update(target_start=show(left), target_end=show(right), **frames(edit, start, end))
    return result


def frames(edit, start, end):
    return dict(frame_in=ceil(edit['target'] + (start - edit['start']) * RATIO),
                frame_out=ceil(edit['target'] + (end - edit['start']) * RATIO))


def recap_pairs(fragments, edit_list):
    cuts = {edit['cut']: edit for edit in edit_list}
    keeps = [row for row in fragments if row['kind'] == 'KEEP']
    pairs = []
    for row in fragments:
        if row['kind'] != 'RECAP':
            continue
        recap = cuts[row['cut']]
        start, end = Fraction(row['start']), Fraction(row['end'])
        for other in keeps:
            if (other['cue_id'], other['track']) != (row['cue_id'], row['track']):
                continue
            left, right = max(start, Fraction(other['start'])), min(end, Fraction(other['end']))
            if left >= right:
                continue
            keep = cuts[other['cut']]
            pairs.append(dict(cue_id=row['cue_id'], track=row['track'], line=row['line'],
                              start=show(left), end=show(right),
                              original=dict(cut=keep['cut'], **frames(keep, left, right)),
                              recap=dict(cut=recap['cut'], **frames(recap, left, right))))
    return pairs
