import React, { useEffect } from "react";
import { X } from "lucide-react";

export const pct = (value, digits = 2) =>
  value == null
    ? "Unavailable"
    : `${Number(value).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
export const money = (value) =>
  value == null
    ? "Unavailable"
    : Number(value).toLocaleString("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      });
export const human = (value) => String(value || "").replaceAll("_", " ");

export async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
  });
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(
      "The server is temporarily unavailable. Please try again; no review will be resubmitted automatically.",
    );
  }
  if (!response.ok)
    throw new Error(
      Array.isArray(body.detail)
        ? body.detail
            .map((item) => `${item.location}: ${item.message}`)
            .join("\n")
        : body.detail || "The request could not be completed.",
    );
  return body;
}

export function Dialog({ title, children, close, wide = false }) {
  const ref = React.useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    ref.current?.showModal();
    return () => previous?.focus();
  }, []);
  return (
    <dialog
      ref={ref}
      aria-label={title}
      className={`modal ${wide ? "wide" : ""}`}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClick={(event) => {
        if (event.target === ref.current) close();
      }}
    >
      <div className="modal-title">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={close}
          aria-label="Close dialog"
        >
          <X size={21} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
