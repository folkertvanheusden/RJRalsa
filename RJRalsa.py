#! /usr/bin/python3

# (C) 2021 by folkert@vanheusden.com

import getopt
import mido
import queue
import sys
import threading
import time

# after this many seconds of nothing played, the
# midi-file will be closed (after which a new one
# will be created)
inactivity = 1 * 60  # in seconds

# this is a maximum. if you go faster, then increase
# this number
bpm = 960

ppqn = 64

# minimum size of output
min_size = 0

rtmidi = mido.Backend('mido.backends.rtmidi')
input_ = rtmidi.open_input('RJRalsa', virtual=True)

def listener(q, input_):
    while True:
        m = input_.receive()
        t = time.time()

        q.put((m, t))

def start_file():
    tm = time.localtime()
    name = f'recording_{tm.tm_year}-{tm.tm_mon:02d}-{tm.tm_mday:02d}_{tm.tm_hour:02d}-{tm.tm_min:02d}-{tm.tm_sec:02d}.mid'

    track = mido.MidiTrack()

    track.append(mido.MetaMessage('copyright', text='RJRalsa (C) 2021 by folkert@vanheusden.com'))

    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))

    return (track, name)

def end_file(pars):
    mid = mido.MidiFile(ticks_per_beat=ppqn)

    if len(pars[0]) >= min_size:
        mid.tracks.append(pars[0])
        mid.save(pars[1])

    else:
        print(f'Not storing file: not long enough (is {len(pars[0])} MIDI messages in length currently)')

def t_to_tick(ts, p_ts):
    return int(mido.second2tick(ts - p_ts, ppqn, mido.bpm2tempo(bpm)))

def usage():
    print('-i x   inactivity timer (in seconds, optional)')
    print('-b x   BPM (optional)')
    print('-q x   PPQN (optional)')
    print('-n x   minimum size, in notes (optional)')

try:
    opts, args = getopt.getopt(sys.argv[1:], 'i:b:q:n:h')

except getopt.GetoptError as err:
    print(err)
    usage()
    sys.exit(1)

for o, a in opts:
    if o in ("-i"):
        inactivity = float(a)

    elif o in ("-b"):
        bpm = a

    elif o in ("-q"):
        ppqn = a

    elif o in ("-n"):
        min_size = int(a)

    elif o in ("-h"):
       usage()
       sys.exit(0)

    else:
        usage()
        assert False, "unhandled option"

state = None

q = queue.Queue()

t = threading.Thread(target=listener, args=(q, input_,))
t.start()

while True:
    # end file after x seconds of silence
    if state and time.time() - state['latest_msg'] >= inactivity:
        end_file(state['file'])
        print(f"{time.ctime()}] File {state['file'][1]} ended")
        state = None
        continue

    try:
        item = q.get(timeout=0.5)

    except queue.Empty:
        continue

    except KeyboardInterrupt:
        print('Terminating application')
        if state:
            end_file(state['file'])
        break

    if not item:
        if state:
            end_file(state['file'])
        state = None
        break

    if state == None:
        state = dict()
        state['latest_msg'] = state['started_at'] = item[1]
        state['file'] = start_file()
        print(f"{time.ctime()}] Started recording to {state['file'][1]}")

    item[0].time = t_to_tick(item[1], state['latest_msg'])
    print(item)
    state['file'][0].append(item[0])

    state['latest_msg'] = item[1]

input_.close()

t.join()

sys.exit(0)
