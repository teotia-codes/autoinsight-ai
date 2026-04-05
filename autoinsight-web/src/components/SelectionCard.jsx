export default function SectionCard({ title, children, className = "" }) {
  return (
    <div className={`bg-white rounded-2xl shadow-md border border-slate-200 p-5 ${className}`}>
      <h2 className="text-lg font-semibold text-slate-800 mb-4">{title}</h2>
      {children}
    </div>
  );
}