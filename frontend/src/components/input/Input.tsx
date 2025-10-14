import React from "react";

interface InputProps {
  type?: "text" | "password" | "email" | "number" | "tel" | "date";
  name: string;
  placeholder?: string;
  value: string;
  border?: boolean;
  required?: boolean;
  disabled?: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
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
}: InputProps) {
  const baseClasses = `
    text-gray-700 bg-white rounded-full
    transition-all duration-200 focus:outline-none
    focus:ring-2 focus:ring-[#FF4124] hover:border-[#FF4124]
    disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed
    placeholder:text-gray-400 text-sm px-4 py-2 w-full
  `;

  const borderClasses = border
    ? "border border-gray-200 focus:border-[#FF4124]"
    : "";

  const className = `${baseClasses} ${borderClasses}`.trim();

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
    />
  );
}
