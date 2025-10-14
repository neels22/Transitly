import { useNavigate } from 'react-router-dom';
import hamburgerIcon from "../../../assets/hamburger.svg"; 

export default function Header() {
  const navigate = useNavigate();

  const handleHomepageClick = () => {
    navigate('/');
  };

  const handleMenuClick = () => {
    console.log("Menu clicked");
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
        <button
          onClick={handleMenuClick}
          className="focus:outline-none"
        >
          <img
            src={hamburgerIcon}
            alt="Menu"
            className="h-7 w-7"
          />
        </button>
      </div>
    </header>
  );
}
