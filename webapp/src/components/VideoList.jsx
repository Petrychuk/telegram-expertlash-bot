import VideoItem from "./VideoItem";

export default function VideoList({ videos, token, onRefresh }) {
  return (
    <div className="grid gap-3">
      {videos.map(v => (
        <VideoItem key={v.id} v={v} token={token} onRated={onRefresh} />
      ))}
    </div>
  );
}
