import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import './App.css'
import Header from "./components/header/Header.tsx"
import SignIn from "./pages/signIn/SignIn.tsx";
import SignUp from "./pages/signUp/SignUp.tsx";
import ConfirmEmail from "./pages/confirmEmail";
import Home from './pages/Home';

function App() {

  return (
    <Router>
      <div className="App min-h-screen relative">
        <Header />
        <Routes>
          <Route path="/" element={<Navigate to="/home" replace />} /> {}
          <Route path="/sign-in" element={<SignIn />} />
          <Route path="/sign-up" element={<SignUp />} />
          <Route path="/confirm-email" element={<ConfirmEmail />} />
          <Route path="/home" element={<Home />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
