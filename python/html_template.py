#!/usr/bin/env python
#HTML template for Mode S map display
#Nick Foster, 2013

def html_template(my_position, json_file):
    if my_position is None:
        my_position = [37, -122]

    return """
<html>
    <head>
        <title>ADS-B Aircraft Map</title>
        <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
        <meta http-equiv="content-type" content="text/html;charset=utf-8" />
        <style type="text/css">
            .labels {
                color: blue;
                background-color: white;
                font-family: "Lucida Grande", "Arial", sans-serif;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
                width: 70px;
                border: none;
                white-space: nowrap;
            }
        </style>
        <script type="text/javascript" src="http://maps.google.com/maps/api/js?sensor=false">
        </script>
        <script type="text/javascript" src="http://google-maps-utility-library-v3.googlecode.com/svn/tags/markerwithlabel/1.1.9/src/markerwithlabel.js">
        </script>
        <script type="text/javascript">
            var map;
            var markers = [];
            var defaultLocation = new google.maps.LatLng(%f, %f);
            var defaultZoomLevel = 9;

            function requestJSONP() {
                var script = document.createElement("script");
                script.src = "%s?" + Math.random();
                script.params = Math.random();
                document.getElementsByTagName('head')[0].appendChild(script);
            };

            var planeMarker;
            var planes = [];

            function clearMarkers() {
                for (var i = 0; i < planes.length; i++) {
                    planes[i].setMap(null);
                }
                planes = [];
            };

            function jsonp_callback(results) { // from JSONP
                airplanes = {};
                for (var i = 0; i < results.length; i++) {
                    airplanes[results[i].icao] = {
                        center: new google.maps.LatLng(results[i].lat, results[i].lon),
                        heading: results[i].hdg,
                        altitude: results[i].alt,
                        type: results[i].type,
                        ident: results[i].ident,
                        speed: results[i].speed,
                        vertical: results[i].vertical,
                        highlight: results[i].highlight
                    };
                }
//                clearMarkers();
                refreshIcons();
            }

            function refreshIcons() {
                //prune the list
                for(var i = 0; i < planes.length; i++) {
                    icao = planes[i].get("icao")
                    if(!(icao in airplanes)) {
                        planes[i].setMap(null)
                        planes.splice(i, 1);
                    };
                };

                for (var airplane in airplanes) {
                    if (airplanes[airplane].highlight != 0) {
                        icon_file = "http://www.nerdnetworks.org/~bistromath/airplane_sprite_highlight.png";
                    } else {
                        icon_file = "http://www.nerdnetworks.org/~bistromath/airplane_sprite.png";
                    };
                    var plane_icon = {
                        url: icon_file,
                        size: new google.maps.Size(128,128),
                        origin: new google.maps.Point(parseInt(airplanes[airplane].heading/10)*128,0),
                        anchor: new google.maps.Point(64,64),
                        //scaledSize: new google.maps.Size(4608,126)
                    };

                    if (airplanes[airplane].ident.length != 8) {
                        identstr = airplane;
                    } else {
                        identstr = airplanes[airplane].ident;
                    };

                    var planeOptions = {
                        map: map,
                        position: airplanes[airplane].center,
                        icao: airplane,
                        icon: plane_icon,
                        labelContent: identstr,
                        labelAnchor: new google.maps.Point(35, -32),
                        labelClass: "labels",
                        labelStyle: {opacity: 0.75}
                    };

                    var i = 0;
                    for(i; i<planes.length; i++) {
                        if(planes[i].get("icao") == airplane) {
                            planes[i].setPosition(airplanes[airplane].center);
                            if(planes[i].get("icon") != plane_icon) {
                                planes[i].setIcon(plane_icon); //handles highlight and heading
                            };
                            if(planes[i].get("labelContent") != identstr) {
                                planes[i].set("labelContent", identstr);
                            };
                            break;
                        };
                    };
                    if(i == planes.length) {
                        planeMarker = new MarkerWithLabel(planeOptions);
                        planes.push(planeMarker);
                    };
                };
            };

            function initialize()
            {
                var myOptions =
                {
                    zoom: defaultZoomLevel,
                    center: defaultLocation,
                    disableDefaultUI: true,
                    mapTypeId: google.maps.MapTypeId.TERRAIN
                };

                map = new google.maps.Map(document.getElementById("map_canvas"), myOptions);

                requestJSONP();
                setInterval("requestJSONP()", 1000);
            };
        </script>
    </head>
    <body onload="initialize()">
        <div id="map_canvas" style="width:100%%; height:100%%">
        </div>
    </body>
</html>""" % (my_position[0], my_position[1], json_file)
