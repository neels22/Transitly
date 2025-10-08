import { useNavigate } from 'react-router-dom';
import Button from "../button";

export default function Header() {
  const navigate = useNavigate();

  return (
    <header className="flex justify-between items-center px-6 py-0 bg-white">
      <div className="flex items-center">
        <img
          src="/assets/full-logo.svg"
          alt="Campus Marketplace"
          className="h-10 w-auto cursor-pointer"
          onClick={() => navigate('/')}
        />
      </div>
      <div className="flex items-center space-x-4">
        <Button text="Sign In"/>
      </div>
    </header>
  );
}