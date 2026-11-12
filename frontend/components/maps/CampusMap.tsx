"use client";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";

export const STATUS_COLOR: Record<string, string> = { normal: "#16a34a", elevated: "#eab308", anomaly: "#dc2626", no_data: "#94a3b8" };

export default function CampusMap({ buildings, solar, selected, onSelect }: { buildings: any[]; solar: string[]; selected?: number; onSelect: (b: any) => void }) {
  const pts = buildings.filter((b) => b.lat && b.lon);
  const center: [number, number] = pts.length ? [pts.reduce((s, b) => s + b.lat, 0) / pts.length, pts.reduce((s, b) => s + b.lon, 0) / pts.length] : [22.2536, 84.9006];
  return (
    <MapContainer center={center} zoom={16} className="h-[560px] w-full rounded-xl" scrollWheelZoom>
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {pts.map((b) => (
        <CircleMarker key={b.building_id} center={[b.lat, b.lon]} radius={b.building_id === selected ? 13 : 9}
          pathOptions={{ color: solar.includes(b.building) ? "#2563eb" : "#fff", weight: solar.includes(b.building) ? 3 : 2, fillColor: STATUS_COLOR[b.status], fillOpacity: 0.95 }}
          eventHandlers={{ click: () => onSelect(b) }}>
          <Tooltip>{b.building} ({b.zone})</Tooltip>
          <Popup>{b.building}</Popup>
        </CircleMarker>))}
    </MapContainer>
  );
}
