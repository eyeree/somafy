Populate [Spotify](https://www.spotify.com/us/) playlists with all tracks from albums played on [SomaFM](https://somafm.com) channels by doing the following:
1. for a set of configured SomaFM channels...
1. create a spotify playlist for that channel if it doesn't exist
1. read recenttly played album and artist from somafm website
1. lookup album/artist in mapping.json to see if it has been processed before, if it has been processed its entry in mappings.json will be the matching spotify album id or null if there is no matching album
1. if the album/artist has been process before then stop and do the next album/arist or channel
1. get list of tracks already on spotify playlist and remove any duplicates (in case mappings.json is out of sync)
1. add tracks to beginning of spotify playlist
