export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export const moveService = {
  submitMove: async (data: {
    from_address: string;
    to_address: string;
    move_out_date: string;
    move_in_date: string;
  }) => {
    const token = localStorage.getItem("id_token");

    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/move`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify(data)
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      const msg = errBody.detail || "Failed to submit move.";
      throw new ApiError(msg);
    }

    return res.json();
  }
};
