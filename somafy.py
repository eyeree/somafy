from bs4 import BeautifulSoup
import requests
import dateparser
import editdistance
import json
import os
import random
import spotipy
import sys
import time

FIND_DELAY = 0.25   # seconds
MIN_LONG_SLEEP = 5  # minutes
MAX_LONG_SLEEP = 20 # minutes

SPOTIFY_USER_NAME = os.environ.get('SPOTIFY_USER_NAME')
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')

if SPOTIFY_USER_NAME is None or SPOTIFY_CLIENT_ID is None or SPOTIFY_CLIENT_SECRET is None:
    print('')
    print('You need set envionment variables:')
    print('')
    print('export SPOTIFY_USER_NAME=')
    print('export SPOTIFY_CLIENT_ID=')
    print('export SPOTIFY_CLIENT_SECRET=')
    print('')
    exit(1)

SPOTIFY_REDIRECT_URL = 'http://localhost:9090'
SPOTIFY_SCOPE = 'playlist-modify-public playlist-read-private'

SOMAFM_CHANNELS = [
    'deepspaceone',
    'dronezone',
    'fluid',
    'groovesalad',
    'gsclassic',
    'lush',
    'sonicuniverse',
    'spacestation',
    'suburbsofgoa'
]

sp = None
mapping = None


def q(s):
    return '"{}"'.format(s)
    

def sp_page(result):
    yield result
    while result['next']:
        result = sp.next(result)
        yield result


def init_spotify():

    token = spotipy.util.prompt_for_user_token(
        SPOTIFY_USER_NAME, 
        SPOTIFY_SCOPE,
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URL)

    if not token:
        print("Can't get token for", SPOTIFY_USER_NAME)
        exit(1)

    sp = spotipy.Spotify(auth=token)
    sp.trace = False

    print('init_spotify', SPOTIFY_USER_NAME)

    return sp


def get_somafm_list(channel):

    URL = 'https://somafm.com/{}/songhistory.html'.format(channel)
    page = requests.get(URL)

    soup = BeautifulSoup(page.content, 'html.parser')

    somafm_list = {'channel': channel}

    somafm_list['title'] = soup.find(id='channelblock').find('h1').text.strip()

    table = soup.find(id='playinc').find('table')
    somafm_list['tracks'] = []

    for row in table.findAll('tr')[1:]:
        cols = row.findAll('td')
        if(len(cols) == 5):
            somafm_list['tracks'].append({
                'artist': cols[1].text,
                'track': cols[2].text,
                'album': cols[3].text
            })

    print('get_somafm_list', channel, q(somafm_list['title']), len(somafm_list['tracks']), 'tracks')

    return somafm_list


def load_mapping():
    return json.loads(open('mapping.json').read())


def save_mapping(mapping):
    with open('mapping.json', 'w') as outfile:
        json.dump(mapping, outfile, indent=4)


def get_mapping_key(somafm_track):
    return '{} - {}'.format(somafm_track['artist'], somafm_track['album'])


def get_channel_mapping(somafm_list):
    channel = somafm_list['channel']
    if channel not in mapping:
        mapping[channel] = {}
    return mapping[channel]


def is_mapped(somafm_list, somafm_track):
    channel_mapping = get_channel_mapping(somafm_list)
    key = get_mapping_key(somafm_track)
    return key in channel_mapping


def add_mapping(somafm_list, somafm_track, spotify_album):
    channel_mapping = get_channel_mapping(somafm_list)
    key = get_mapping_key(somafm_track)
    if spotify_album:
        channel_mapping[key] = spotify_album['id']
    else:
        channel_mapping[key] = None


def filter_somafm_list(somafm_list):
    somafm_list['tracks'] = [t for t in somafm_list['tracks'] if not is_mapped(somafm_list, t)]
    print('filter_somafm_list', somafm_list['channel'], q(somafm_list['title']), len(somafm_list['tracks']), 'new tracks')


def filter_albums_by_artist_edit_distance(albums, somafm_track):
    min_artist_ed = None
    for album in albums:
        artist_ed = None
        for artist in album['artists']:
            ed = editdistance.eval(somafm_track['artist'], artist['name'])
            if artist_ed is None or ed < artist_ed:
                artist_ed = ed
        if min_artist_ed is None or artist_ed < min_artist_ed:
            min_artist_ed = artist_ed
        print('  ???', albums[0]['name'], [a['name'] for a in albums[0]['artists']], 'artist_ed', artist_ed)
        album['artist_ed'] = artist_ed
    return [a for a in albums if a['artist_ed'] == min_artist_ed]


def filter_albums_by_name_edit_distance(albums, somafm_track):
    min_album_ed = None
    for album in albums:
        album_ed = editdistance.eval(album['name'], somafm_track['album'])
        if min_album_ed is None or album_ed < min_album_ed:
            min_album_ed = album_ed
        print('  ???', album['name'], 'album_ed', album_ed)
        album['album_ed'] = album_ed
    return [a for a in albums if a['album_ed'] == min_album_ed]


def filter_albums_by_release_date(albums):
    max_release_date = None
    for album in albums:
        release_date = dateparser.parse(album['release_date'])
        album['parsed_release_date'] = release_date
        print('  ???', albums[0]['name'], [a['name'] for a in albums[0]['artists']], 'release_date', release_date)
        if max_release_date is None or release_date > max_release_date:
            max_release_date = release_date
    return [a for a in albums if a['parsed_release_date'] == max_release_date]


def find_spotify_album(somafm_track):
    
    print('find_spotify_album', q(somafm_track['track']), 'on', q(somafm_track['album']), 'by', q(somafm_track['artist']))

    time.sleep(FIND_DELAY)

    query = 'album:{} artist:{}'.format(somafm_track['album'], somafm_track['artist'])
    result = sp.search(query, type='album')
    albums = result['albums']['items']

    if len(albums) == 0:
        return None

    if len(albums) == 1:
        print('  -->', albums[0]['name'], [a['name'] for a in albums[0]['artists']], '*** only')
        return albums[0]

    albums = filter_albums_by_artist_edit_distance(albums, somafm_track)

    if len(albums) == 1:
        print('  -->', albums[0]['name'], [a['name'] for a in albums[0]['artists']], '*** artist ed')
        return albums[0]

    albums = filter_albums_by_name_edit_distance(albums, somafm_track)

    if len(albums) == 1:
        print('  -->', albums[0]['name'], [a['name'] for a in albums[0]['artists']], '*** album ed')
        return albums[0]

    albums = filter_albums_by_release_date(albums)

    if len(albums) == 1:
        print('  -->', albums[0]['name'], [a['name'] for a in albums[0]['artists']], albums[0]['parsed_release_date'], '*** release date' )
        return albums[0]

    print('  -->', albums[0]['name'], [a['name'] for a in albums[0]['artists']], '*** first result', '<<<<<<<<<<<<<<<<<<<<<<<<')
    
    return albums[0]


def get_spotify_album_tracks(spotify_album):
    result = []
    for page in sp_page(sp.album_tracks(spotify_album['id'])):
        result.extend(page['items'])
    print('get_spotify_album_tracks', q(spotify_album['name']), len(result), 'tracks')
    return [t['id'] for t in result]


def get_spotify_playlist_tracks(spotify_list):
    if 'track_ids' not in spotify_list:
        result = set()
        for page in sp_page(sp.playlist_tracks(spotify_list['id'])):
            for item in page['items']:
                result.add(item['track']['id'])
        spotify_list['track_ids'] = result
        print('get_spotify_playlist_tracks', q(spotify_list['name']), len(result), 'tracks')
    return spotify_list['track_ids']


def filter_tracks_by_spotify_list(spotify_album, album_tracks, spotify_list):
    list_tracks = get_spotify_playlist_tracks(spotify_list)
    duplicates = [id for id in album_tracks if id in list_tracks]
    if(len(duplicates) > 0):
        print('filter_tracks_by_spotify_list', q(spotify_list['name']), 'duplicated', q(spotify_album['name']), 'with', len(duplicates), 'tracks')
    return [id for id in album_tracks if id not in list_tracks]


def add_spotify_album_to_list(spotify_album, spotify_list):
    tracks = get_spotify_album_tracks(spotify_album)
    tracks = filter_tracks_by_spotify_list(spotify_album, tracks, spotify_list)
    if len(tracks) > 0:
        user = sp.current_user()
        sp.user_playlist_add_tracks(user['id'], spotify_list['id'], tracks, position=0)
        print('add_spotify_album_to_list', q(spotify_list['name']), 'added', q(spotify_album['name']), 'with', len(tracks), 'tracks')


def update_spotify_list(spotify_list, somafm_list):
    print('update_spotify_list', q(spotify_list['name']), len(somafm_list['tracks']), 'new tracks')
    for somafm_track in somafm_list['tracks']:
        spotify_album = find_spotify_album(somafm_track)
        if spotify_album:
            add_spotify_album_to_list(spotify_album, spotify_list)
            add_mapping(somafm_list, somafm_track, spotify_album)
        else:
            add_mapping(somafm_list, somafm_track, None)


def create_spotify_list(name, title):
    user = sp.current_user()
    result = sp.user_playlist_create(user['id'], name, public=True, 
        description='All tracks from albums played on the SomaFM {} channel.'.format(title))
    print('create_spotify_list', q(name), result['id'])
    return result


def get_spotify_list(spotify_lists, somafm_list):
    name = 'SomaFM {} Albums'.format(somafm_list['title'])
    if not name in spotify_lists:
        spotify_lists[name] = create_spotify_list(name, somafm_list['title'])
    result = spotify_lists[name]
    print('get_spotify_list', q(name), result['id'])
    return result


def get_spotify_lists():
    spotify_lists = {}
    for result in sp_page(sp.current_user_playlists()):
        for item in result['items']:
            spotify_lists[item['name']] = item
    print('get_spotify_lists', len(spotify_lists), 'lists')
    return spotify_lists


def update_all():

    global mapping, sp
    mapping = load_mapping()
    sp = init_spotify()
    
    spotify_lists = get_spotify_lists()
    for channel in SOMAFM_CHANNELS:
        somafm_list = get_somafm_list(channel)
        filter_somafm_list(somafm_list)
        if(len(somafm_list['tracks']) > 0):
            spotify_list = get_spotify_list(spotify_lists, somafm_list)
            update_spotify_list(spotify_list, somafm_list)

    save_mapping(mapping)


def long_sleep(minutes):
    seconds = minutes * 60
    print()
    while seconds > 0:
        print('  waiting', seconds, 'seconds      ', end = '\r')
        time.sleep(10)
        seconds -= 10


while True:
    update_all()
    long_sleep(random.randrange(MIN_LONG_SLEEP, MAX_LONG_SLEEP))
