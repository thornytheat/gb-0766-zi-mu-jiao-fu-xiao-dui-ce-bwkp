import pytest
from app.modules.edits.contract import timeline
from app.pipeline import inspect
from app.problems import Rejection

RECAP_CUES = ('cue_id,track,format,in,out,text\n'
              'C1,简中,FRAME,100,200,甲\nC2,简中,FRAME,150,250,乙\nC3,简中,FRAME,300,400,丙\n')
RECAP_CUTS = 'cut,start,end,target,kind\nA,0,500,0,KEEP\nR,100,200,1000,RECAP\n'


def test_cross_cut_retains_source_line(dirty):
    assert [(x['kind'], x['line'], x['start'], x['end']) for x in dirty['edits']['rows'] if x['cue_id']=='C101'] == [
        ('KEEP',2,'900','1000'), ('REMOVE',2,'1000','1200'), ('KEEP',2,'1200','1300')]


def test_unknown_gap(dirty):
    row, = [x for x in dirty['edits']['rows'] if x['kind']=='GAP']
    assert (row['cue_id'], row['start'], row['end'], row['cut_line']) == ('C103','2000','2200',None)


def test_edl_source_collision():
    with pytest.raises(Rejection) as error:
        timeline('cut,start,end,target,kind\nA,1,100,0,KEEP\nB,99,110,,REMOVE\n')
    assert error.value.code == 'CUT_OVERLAP'


def test_edl_target_collision():
    with pytest.raises(Rejection) as error:
        timeline('cut,start,end,target,kind\nA,1,100,0,KEEP\nB,100,110,50,KEEP\n')
    assert error.value.code == 'TARGET_OVERLAP'


def test_cut_target_anchor(dirty):
    row = next(x for x in dirty['edits']['rows'] if x['cue_id']=='C101' and x['cut']=='B-01')
    assert (row['frame_in'], row['frame_out'], row['cut_line']) == (810,891,4)


def test_remove_has_no_target(dirty):
    assert all('frame_in' not in row for row in dirty['edits']['rows'] if row['kind']=='REMOVE')


def test_recap_repeats_cue_with_original_line():
    rows = inspect(dict(cues=RECAP_CUES, cuts=RECAP_CUTS))['edits']['rows']
    c1 = [(x['kind'], x['cut'], x['frame_in'], x['frame_out'], x['line']) for x in rows if x['cue_id']=='C1']
    assert c1 == [('KEEP','A',81,161,2), ('RECAP','R',1000,1081,2)]
    assert all(x['text'] == '甲' for x in rows if x['cue_id']=='C1')


def test_recap_counts(dirty):
    assert dirty['edits']['counts'] == {'KEEP': 16, 'REMOVE': 2, 'RECAP': 0, 'GAP': 1}


def test_recap_partial_segment_pairs():
    cuts = 'cut,start,end,target,kind\nA,0,500,0,KEEP\nR,150,250,1000,RECAP\n'
    pairs = inspect(dict(cues=RECAP_CUES, cuts=cuts))['edits']['recaps']
    assert [(p['line'], p['start'], p['end']) for p in pairs] == [(2,'150','200'), (3,'150','250')]
    assert pairs[0]['original'] == dict(cut='A', frame_in=121, frame_out=161)
    assert pairs[0]['recap'] == dict(cut='R', frame_in=1000, frame_out=1041)


def test_recap_spanning_keeps_pairs():
    cues = 'cue_id,track,format,in,out,text\nC9,简中,FRAME,900,1100,跨段\n'
    cuts = ('cut,start,end,target,kind\n'
            'A,0,1000,0,KEEP\nB,1000,1500,810,KEEP\nR,900,1100,2000,RECAP\n')
    pairs = inspect(dict(cues=cues, cuts=cuts))['edits']['recaps']
    assert [(p['original']['cut'], p['original']['frame_in'], p['original']['frame_out'],
             p['recap']['frame_in'], p['recap']['frame_out']) for p in pairs] == [
        ('A',721,801,2000,2081), ('B',810,891,2081,2161)]
    assert [p['line'] for p in pairs] == [2, 2]


def test_recap_outside_keep_rejected():
    with pytest.raises(Rejection) as error:
        timeline('cut,start,end,target,kind\nA,0,1000,0,KEEP\nB,1000,1200,,REMOVE\nR,900,1100,2000,RECAP\n')
    assert error.value.code == 'RECAP_SOURCE'


def test_recap_over_removed_rejected():
    with pytest.raises(Rejection) as error:
        timeline('cut,start,end,target,kind\nA,0,100,0,KEEP\nM,100,200,,REMOVE\nR,100,150,500,RECAP\n')
    assert error.value.code == 'RECAP_SOURCE'


def test_recap_source_collision():
    with pytest.raises(Rejection) as error:
        timeline('cut,start,end,target,kind\nA,0,1000,0,KEEP\nR1,100,200,2000,RECAP\nR2,150,250,3000,RECAP\n')
    assert error.value.code == 'CUT_OVERLAP'


def test_recap_target_collision():
    with pytest.raises(Rejection) as error:
        timeline('cut,start,end,target,kind\nA,0,1000,0,KEEP\nR,100,200,500,RECAP\n')
    assert error.value.code == 'TARGET_OVERLAP'


def test_recap_target_collision_between_recaps():
    with pytest.raises(Rejection) as error:
        timeline('cut,start,end,target,kind\nA,0,1000,0,KEEP\nR1,100,150,2000,RECAP\nR2,200,250,2010,RECAP\n')
    assert error.value.code == 'TARGET_OVERLAP'


def test_recap_needs_target():
    with pytest.raises(Rejection) as error:
        timeline('cut,start,end,target,kind\nA,0,1000,0,KEEP\nR,100,200,,RECAP\n')
    assert error.value.code == 'CUT_RANGE'
