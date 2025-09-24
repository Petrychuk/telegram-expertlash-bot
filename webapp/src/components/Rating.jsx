export default function Rating({ value=0, onChange }) {
  return (
    <div className="flex gap-1">
      {[1,2,3,4,5].map(n => (
        <button key={n} onClick={() => onChange?.(n)} className="p-1">
          <span className={n <= value ? "text-roseSoft-600" : "text-roseSoft-300"}>★</span>
        </button>
      ))}
    </div>
  );
}
