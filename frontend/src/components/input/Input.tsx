import React from "react";

interface InputProps {
  type?: "text" | "password" | "email" | "number" | "tel" | "date";
  // make name optional for visual-only inputs
  name?: string;
  placeholder?: string;
  value: string;
  border?: boolean;
  required?: boolean;
  disabled?: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  width?: string;
  size?: "sm" | "md" | "lg";
}

export default function Input({
  type = "text",
  name,
  placeholder,
  value,
  border = true,
  required = false,
  disabled = false,
  onChange,
  width,
  size = "md",
}: InputProps) {
  const sizeClasses = {
    sm: "text-sm px-3 py-1",
    md: "text-sm px-4 py-2",
    lg: "text-base px-5 py-3",
  }[size];

  const baseClasses = `
    text-gray-700 bg-white rounded-full
    transition-all duration-200 focus:outline-none
    focus:ring-2 focus:ring-[#FF4124] hover:border-[#FF4124]
    disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed
    placeholder:text-gray-400 ${sizeClasses}
  `;

  const borderClasses = border
    ? "border border-gray-200 focus:border-[#FF4124]"
    : "";

  const className = `${baseClasses} ${borderClasses}`.trim();

  const style = width ? { width } : undefined;

  return (
    <input
      type={type}
      name={name}
      placeholder={placeholder}
      value={value}
      className={className}
      required={required}
      disabled={disabled}
      onChange={onChange}
      autoComplete="off"
      style={style}
    />
  );
}
