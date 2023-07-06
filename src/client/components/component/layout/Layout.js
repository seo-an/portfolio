// import { Outlet } from 'react-router-dom';
import { useEffect, useState, useRef } from 'react';

import Nav from './Nav';
import { Footer } from './Footer';
import Main from './Main';

import { MainContainer as Container, MainGrid as Grid } from '../../view/layout/LayoutGridView';


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
      <Container ref={containerHeight}>
        <Grid>
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
        </Grid>
      </Container>
    </>
  )
}

export default Layout;