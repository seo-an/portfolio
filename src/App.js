import { BrowserRouter, Route, Routes } from "react-router-dom";

import Layout from "./client/view/layout/Layout";
import Home from "./client/view/routes/Home";
import OpenApiPage from "./client/view/routes/OpenApiPage";
import RestApiPage from "./client/view/routes/RestApiPage";
import About from "./client/view/routes/About";

import { Calendar } from "./client/components/component/CalendarJs";
import { SvgImg } from "./client/components/component/SvgImgJs";
// import TestComponent from "./test/TestComponent";
// import { as TestComponent} from "";


export default function App() {
  const ready = process.env.REACT_APP_IS_READY;

  return (
    <>
      <BrowserRouter basename="/">
        <Routes>
          <Route exact path="/" element={<Layout />}>
            <Route index element={<Home />}></Route>
            <Route path="/home" element={<Home />}></Route>
            <Route path="/handle-open-api" element={<OpenApiPage />}></Route>
            <Route path="/handle-rest-api" element={<RestApiPage />}></Route>
            <Route path="/about" element={<About />}></Route>

            <Route path="/calendar" element={<Calendar />}></Route>
            <Route path="/svg-component" element={<SvgImg />}></Route>
          </Route>
          <Route path="*" element={<h1>Error 404</h1>}></Route>
        </Routes>
      </BrowserRouter>
    </>
  );
}