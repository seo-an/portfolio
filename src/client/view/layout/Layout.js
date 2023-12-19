import { useEffect, useState, useRef } from 'react';

import styled from 'styled-components';

import Nav from './Nav.js';
import { Footer } from './Footer.js';
import Main from './Main.js';


export const min = 780;
export const hd = 1280; // 1280*720
export const fhd = 1920; // 1920*1080
export const qhd = 2048; // 2560*1440
export const uhd = 3839; // 3840*2160
// max, min-max, min


export const MainContainer = styled.div `
  display: flex;
  justify-content: center;


`

export const MainGrid = styled.div `
  display: grid;
  width: 100%;
  min-width: ${min}px;
  max-width: ${hd}px;

  @media screen and (max-width: ${hd}px) {
    // background-color: linen;
  }

  @media screen and (min-width: ${hd + 1}px) {
    // background-color: pink;
  }
`



const Layout = () => {
  const containerHeight = useRef();

  const [windowHeight, setWindowHeight] = useState(window.innerHeight);
  const [nowHeight, setNowHeight] = useState(0);

  const handleResize = () => {
    setWindowHeight(window.innerHeight);
    // console.log(window.innerWidth);
  };

  useEffect(() => {
    // setWindowHeight(window.innerHeight);
    window.addEventListener("resize", handleResize);
    setNowHeight(containerHeight.current.clientHeight);
    // console.log('window height', windowHeight, 'now height', nowHeight);

    return () => { window.removeEventListener("resize", handleResize); };
  }, [windowHeight, nowHeight]);

  const isScroll = (nowHeight > windowHeight);

  return (
    <>
      <MainContainer ref={containerHeight}>
        <MainGrid>
          {(isScroll ? (
              <>
                <Nav nowScroll={isScroll}/>
                <Main nowScroll={isScroll}/>
                <Footer nowScroll={isScroll}/>
              </>
            ) : (
              <>
                <Nav/>
                <Main />
                <Footer />
              </>
            ))}
        </MainGrid>
      </MainContainer>
    </>
  )
}

export default Layout;