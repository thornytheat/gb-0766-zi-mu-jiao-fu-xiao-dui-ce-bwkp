import pytest
from app.modules.delivery.service import signing
from app.problems import Rejection


def test_download(client, saved):
    response = client.get(f"/api/delivery/{saved['id']}/export")
    assert 'attachment;' in response.headers['Content-Disposition']
    assert response.json['original']['cues'].startswith('\ufefflegacy_id')


def test_archive_stamp(client, saved):
    assert client.get(f"/api/delivery/{saved['id']}").json['certificate'] == saved['manifest']


def test_unknown_delivery(client):
    assert client.get('/api/delivery/none/export').json['code'] == 'NO_RUN'


def test_mutated_original(client, saved):
    entry = client.application.extensions['cut_archive'].read(saved['id'])
    entry['original']['cuts'] += '\n'
    with pytest.raises(Rejection, match='证据散列'):
        signing(entry)


def test_mutated_result(client, saved):
    entry = client.application.extensions['cut_archive'].read(saved['id'])
    entry['stages']['overlaps']['rows'].clear()
    with pytest.raises(Rejection, match='证据散列'):
        signing(entry)


def test_precision_survives_roundtrip(client, saved):
    response = client.get(f"/api/delivery/{saved['id']}/export").json
    assert response['stages']['overlaps']['rows'][-1]['cues'][0] == '9007199254740993'


def test_export_marks_recap_recurrences(client):
    body = dict(cues='cue_id,track,format,in,out,text\nC1,简中,FRAME,100,200,甲\nC2,简中,FRAME,150,250,乙\n',
                cuts='cut,start,end,target,kind\nA,0,500,0,KEEP\nR,150,250,1000,RECAP\n')
    run = client.post('/api/runs', json=body).json
    export = client.get(f"/api/delivery/{run['id']}/export").json
    assert export['verified']
    pairs = export['stages']['edits']['recaps']
    assert [(p['cue_id'], p['line'], p['start'], p['end']) for p in pairs] == [
        ('C1',2,'150','200'), ('C2',3,'150','250')]
    assert pairs[0]['original'] == dict(cut='A', frame_in=121, frame_out=161)
    assert pairs[0]['recap'] == dict(cut='R', frame_in=1000, frame_out=1041)
    assert pairs[1]['recap'] == dict(cut='R', frame_in=1000, frame_out=1081)
