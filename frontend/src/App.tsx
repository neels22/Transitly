import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import './App.css'
import Header from "./components/header/Header.tsx"
import SignIn from "./pages/signIn/SignIn.tsx";
import SignUp from "./pages/signUp/SignUp.tsx";
import ConfirmEmail from "./pages/confirmEmail";

function App() {

  return (
    <Router>
      <div className="App min-h-screen relative">
        <Header />
        <Routes>
          <Route path="/" element={""} />
          <Route path="/sign-in" element={<SignIn />} />
          <Route path="/sign-up" element={<SignUp />} />
          <Route path="/confirm-email" element={<ConfirmEmail />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
