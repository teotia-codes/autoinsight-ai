export default function FileUploadCard({
  title,
  accept,
  file,
  onChange,
  buttonLabel = "Choose File",
  helperText,
}) {
  return (
    <div className="bg-white rounded-2xl shadow-md border border-slate-200 p-5">
      <h3 className="text-lg font-semibold text-slate-800 mb-3">{title}</h3>

      <label className="inline-flex items-center gap-3 px-4 py-2 rounded-xl bg-slate-900 text-white cursor-pointer hover:bg-slate-800 transition">
        <span>{buttonLabel}</span>
        <input
          type="file"
          accept={accept}
          onChange={onChange}
          className="hidden"
        />
      </label>

      {file && (
        <p className="mt-3 text-sm text-emerald-700 font-medium">
          Selected: {file.name}
        </p>
      )}

      {helperText && (
        <p className="mt-2 text-sm text-slate-500">{helperText}</p>
      )}
    </div>
  );
}