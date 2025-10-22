import { useNavigate } from "react-router-dom";
import { useUser } from "../../context/user";
import hamburgerIcon from "../../../assets/hamburger.svg";
import Button from "../button";

export default function Header() {
  const navigate = useNavigate();
  const { user, setUser, setTokens } = useUser();

  const handleHomepageClick = () => {
    navigate("/");
  };

  const handleSignOut = () => {
    // Clear user context
    setUser(null);
    setTokens(null);

    // Clear localStorage
    localStorage.clear();

    // Redirect to sign in
    navigate("/sign-in");
  };

  const handleMenuClick = () => {
    // For now, just sign out
    handleSignOut();
  };

  const handleSignInClick = () => {
    navigate("/sign-in");
  };

  return (
    <header className="flex justify-between items-center px-6 py-0 relative z-[60]">
      <div className="flex items-center">
        <img
          src="/assets/full-logo.svg"
          alt="Campus Marketplace"
          className="h-10 w-auto cursor-pointer"
          onClick={handleHomepageClick}
        />
      </div>
      <div className="flex items-center space-x-4">
        {user ? (
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-700">
              Hi, {user.name?.split(" ")[0]}
            </span>
            <button
              onClick={handleSignOut}
              className="text-sm text-red-600 hover:text-red-700 font-medium transition"
            >
              Sign Out
            </button>
          </div>
        ) : (
          <Button
            text="Sign In"
            size="base"
            color="#FF4124"
            onClick={handleSignInClick}
          />
        )}
      </div>
    </header>
  );
}
