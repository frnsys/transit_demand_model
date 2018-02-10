import React, {Component} from 'react';
import DeckGL, {PolygonLayer} from 'deck.gl';
import TripsLayer from './trips-layer';

const LIGHT_SETTINGS = {
  lightsPosition: [-74.05, 40.7, 8000, -73.5, 41, 5000],
  ambientRatio: 0.05,
  diffuseRatio: 0.6,
  specularRatio: 0.8,
  lightsStrength: [2.0, 0.0, 0.0, 0.0],
  numberOfLights: 2
};


function marker(coord, radius) {
  radius = radius || 0.0001;
  let [lat, lng] = coord;
  return [[lng-radius, lat+radius], [lng+radius, lat+radius], [lng+radius, lat-radius], [lng-radius, lat-radius]];
}


export default class DeckGLOverlay extends Component {
  static get defaultViewport() {
    return {
      // nyc
      // longitude: -74,
      // latitude: 40.72,
      // brasilia
      latitude: -15.7757867,
      longitude: -48.0785375,
      zoom: 13,
      maxZoom: 16,
      pitch: 45,
      bearing: 0
    };
  }

  render() {
    const {viewport, trips, buses, trailLength, time} = this.props;

    if (!trips || !buses) {
      return null;
    }

    const layers = [
      new TripsLayer({
        id: 'trips',
        data: trips,
        getPath: d => d.segments,
        getColor: d => (d.vendor === 0 ? [19, 219, 92] : [23, 184, 190]),
        opacity: 0.3,
        strokeWidth: 2,
        trailLength,
        currentTime: time
      }),
      new PolygonLayer({
        id: 'bus-stops',
        data: buses,
        filled: true,
        stroked: false,
        extruded: true,
        wireframe: false,
        opacity: 0.5,
        getPolygon: d => marker(d),
        getFillColor: d => [44, 152, 234, 255],
        getElevation: d => 100,
        lightSettings: LIGHT_SETTINGS
      })
    ];

    return <DeckGL {...viewport} layers={layers} />;
  }
}
