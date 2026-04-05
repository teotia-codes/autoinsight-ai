export default function LoadingOverlay({ show, text = "Processing..." }) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-xl p-6 min-w-[280px] text-center">
        <div className="w-10 h-10 border-4 border-slate-300 border-t-slate-900 rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-slate-700 font-medium">{text}</p>
      </div>
    </div>
  );
}