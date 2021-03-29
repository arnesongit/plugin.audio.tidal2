# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Arne Svenson
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, unicode_literals

from .common import Const, addon

#------------------------------------------------------------------------------
# Global Definitions
#------------------------------------------------------------------------------

class Msg(object):
    # Settings texts
    i30001 = 30001 # User Account
    i30002 = 30002 # Extended
    i30004 = 30004 # Music Quality
    i30005 = 30005 # Lossless (FLAC,ALAC)
    i30006 = 30006 # High (320 kBit/s)
    i30007 = 30007 # Low (96 kBit/s)
    i30008 = 30008 # Username
    i30009 = 30009 # Password
    i30010 = 30010 # Subscription Type
    i30011 = 30011 # Country for Local Media
    i30012 = 30012 # Hifi
    i30013 = 30013 # Premium
    i30014 = 30014 # Max. number of list items per page
    i30015 = 30015 # Unique Client Key
    i30016 = 30016 # Mark Favorites in Labels
    i30017 = 30017 # Append User Paylist Names to Labels
    i30018 = 30018 # Lossless Streaming Option
    i30019 = 30019 # FLAC 16-Bit
    i30020 = 30020 # ALAC 16-Bit (Apple Lossless)
    i30021 = 30021 # FLAC/MQA 24-Bit (Master Audio) <!-- Old -->
    i30022 = 30022 # RTMP-Protocol for High/Low Quality  <!-- Old -->
    i30023 = 30023 # Show Album Year in Labels
    i30024 = 30024 # Add (MQA) to Master Album Labels
    i30025 = 30025 # Options
    i30026 = 30026 # Use HTTP instead of HLS Steaming (max. 720p) <!-- Old -->
    i30027 = 30027 # Addon-Settings

    # Video Settings
    i30040 = 30040 # Video Quality
    i30041 = 30041 # Max Bandwidth
    i30042 = 30042 # Video (1080p)
    i30043 = 30043 # Video (720p)
    i30044 = 30044 # Video (540p)
    i30045 = 30045 # Video (480p)
    i30046 = 30046 # Video (360p)
    i30047 = 30047 # Video (240p)

    # Program Text
    i30101 = 30101 # Artist
    i30102 = 30102 # Album
    i30103 = 30103 # Playlist
    i30104 = 30104 # Track
    i30105 = 30105 # Video
    i30106 = 30106 # Artists
    i30107 = 30107 # Albums
    i30108 = 30108 # Playlists
    i30109 = 30109 # Tracks
    i30110 = 30110 # Videos
    i30111 = 30111 # New
    i30112 = 30112 # Local
    i30113 = 30113 # Exclusive
    i30114 = 30114 # Recommended
    i30115 = 30115 # Movies
    i30116 = 30116 # Shows
    i30117 = 30117 # Genres
    i30118 = 30118 # Moods
    i30119 = 30119 # Top 20
    i30120 = 30120 # Promotions

    # Main Menu
    i30201 = 30201 # My Music
    i30202 = 30202 # Featured Playlists
    i30203 = 30203 # What's New
    i30206 = 30206 # Search
    i30207 = 30207 # Logout
    i30208 = 30208 # Login (Trial-Mode is active !)
    i30209 = 30209 # Remember login details ?  
    i30210 = 30210 # Authorization problem  
    i30211 = 30211 # TIDAL Rising  
    i30212 = 30212 # Suggestions for me
    i30213 = 30213 # My Playlists
    i30214 = 30214 # Favorite Artists
    i30215 = 30215 # Favorite Albums
    i30216 = 30216 # Favorite Playlists
    i30217 = 30217 # Favorite Tracks
    i30218 = 30218 # Favorite Videos
    i30219 = 30219 # Add to TIDAL Favorites
    i30220 = 30220 # Remove from TIDAL Favorites
    i30221 = 30221 # Show Artist
    i30222 = 30222 # Track Radio
    i30223 = 30223 # Recomended Tracks
    i30224 = 30224 # Recomended Videos
    i30225 = 30225 # Artist Bio
    i30226 = 30226 # Top Tracks
    i30227 = 30227 # Artist Radio
    i30228 = 30228 # Playlists from Artist
    i30229 = 30229 # Similar Artists
    i30230 = 30230 # Summary
    i30231 = 30231 # Added {what}
    i30232 = 30232 # Removed {what}
    i30233 = 30233 # Name of the Playlist
    i30234 = 30234 # Description (optional)
    i30235 = 30235 # Delete Playlist
    i30236 = 30236 # Playlist "{name}" contains {count} items. Are you sure to delete this playlist ?
    i30237 = 30237 # Create new Playlist
    i30238 = 30238 # Choose Playlist
    i30239 = 30239 # Add to Playlist ...
    i30240 = 30240 # Remove from Playlist
    i30241 = 30241 # Are you sure to remove item number {entry} from this playlist ?
    i30242 = 30242 # Stream locked
    i30243 = 30243 # Tracks:{tracks} / Videos:{videos}
    i30244 = 30244 # Next Page ({pos1}-{pos2})
    i30245 = 30245 # Show Album
    i30246 = 30246 # Are you sure to remove the item from this playlist ?
    i30247 = 30247 # Remove from '{name}'
    i30248 = 30248 # Move to Playlist ...
    i30249 = 30249 # Set as Default {what} Playlist
    i30250 = 30250 # Reset Default {what} Playlist
    i30251 = 30251 # Rename Playlist
    i30252 = 30252 # Open Playlist (Audio only)"
    i30253 = 30253 # Login failed !!
    i30254 = 30254 # Open as Track/Video Playlist
    i30255 = 30255 # Open as Album Playlist
    i30256 = 30256 # Streaming Options changed. Please re-login !
    i30257 = 30257 # Execute the re-login now ?
    i30258 = 30258 # Clear Playlist
    i30259 = 30259 # Playlist "{name}" contains {count} items. Are you sure to remove all items from this playlist ?
    i30260 = 30260 # Locked
    i30261 = 30261 # Lock "Search for New Music"
    i30262 = 30262 # Enable "Search for New Music"
    i30263 = 30263 # Adding to Playlist ...
    i30264 = 30264 # Removing from Playlist ...
    i30265 = 30265 # Moving to Playlist ...
    i30266 = 30266 # Deleting from Playlist ...
    i30267 = 30267 # Please wait ...
    i30268 = 30268 # Release Date: {:%m/%d/%Y}
    # New IDs
    i30269 = 30269 # API Call Failed

    # Extended Settings
    i30501 = 30501 # Use Colors in Labels
    i30502 = 30502 # Enable Debug-Logging
    i30503 = 30503 # Read Album Data for every Track (Album Cache)
    i30504 = 30504 # Not a FLAC Stream !
    i30505 = 30505 # Album Cache Error !
    i30506 = 30506 # Max. number of parallel HTTP requests
    i30507 = 30507 # Delete Album Cache
    i30508 = 30508 # Are you sure to delete the Album Cache Database ?
    i30509 = 30509 # Cached Albums with Videos
    i30510 = 30510 # Got no HTTP Stream, using HLS ... <!-- Old -->
    i30511 = 30511 # Activate Fanart HTTP Server
    i30512 = 30512 # IP-Port for Fanart HTTP Server

def _T(txtid):
    if isinstance(txtid, Const.string_types):
        # Map TIDAL texts to Text IDs
        newid = {'artist': Msg.i30101, 'album': Msg.i30102, 'playlist': Msg.i30103, 'track': Msg.i30104, 'video': Msg.i30105,
                 'artists': Msg.i30101, 'albums': Msg.i30102, 'playlists': Msg.i30103, 'tracks': Msg.i30104, 'videos': Msg.i30105,
                 'featured': Msg.i30203, 'rising': Msg.i30211, 'discovery': Msg.i30212, 'movies': Msg.i30115, 'shows': Msg.i30116, 
                 'genres': Msg.i30117, 'moods': Msg.i30118
                 }.get(txtid.lower(), None)
        if not newid: return txtid
        txtid = newid
    try:
        txt = addon.getLocalizedString(txtid)
        return txt
    except:
        return '%s' % txtid


def _P(key, default_txt=None):
    # Plurals of some Texts
    newid = {'new': Msg.i30111, 'local': Msg.i30112, 'exclusive': Msg.i30113, 'recommended': Msg.i30114, 'top': Msg.i30119,
             'artist': Msg.i30106, 'album': Msg.i30107, 'playlist': Msg.i30108, 'track': Msg.i30109, 'video': Msg.i30110,
             'artists': Msg.i30106, 'albums': Msg.i30107, 'playlists': Msg.i30108, 'tracks': Msg.i30109, 'videos': Msg.i30110
             }.get(key.lower(), None)
    if newid:
        return _T(newid)
    return default_txt if default_txt else key

# End of File