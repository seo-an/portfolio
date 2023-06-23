import { BrowserRouter, Route, Routes } from "react-router-dom";

import Layout from "./client/components/component/layout/Layout";

import { Home } from "./client/routes/Home";
import OpenApiPage from "./client/routes/OpenApiPage";
import RestApiPage from "./client/routes/RestApiPage";
import About from "./client/routes/About";



export default function App() {
  return (
    <BrowserRouter basename="/">
			<Routes>
        <Route exact path="/" element={<Layout />}>
          <Route index element={<Home />}></Route>
          <Route path="/home" element={<Home />}></Route>
          <Route path="/handle-open-api" element={<OpenApiPage />}></Route>
          <Route path="/handle-rest-api" element={<RestApiPage />}></Route>
          <Route path="/about" element={<About />}></Route>
        </Route>
        <Route path="*" element={<h1>Error 404</h1>}></Route>
			</Routes>
		</BrowserRouter>
  );
}