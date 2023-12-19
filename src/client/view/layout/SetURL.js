import { Link } from 'react-router-dom';

import { MenuForSetUrl as Menu } from './Nav.js';


const SetURL = () => {
  const data = [
    {
      id: 'home',
      url: '/',
      text: 'Home',
    },
    {
      id: 'handle-open-api',
      url: '/handle-open-api',
      text: 'API 포트폴리오',
    },
    {
      id: 'handle-rest-api',
      url: '/handle-rest-api',
      text: 'REST API 포트폴리오',
    },
    {
      id: 'about',
      url: '/about',
      text: 'About',
    },
  ];

  
  return (
    <>
      {data.map( (dat) => (
        <Menu key={dat.id}>
          {(dat.text === "API 포트폴리오") ? (<Link to={`${dat.url}`}><span>{dat.text}</span></Link>) : (<Link to={`${dat.url}`}><span>{dat.text}</span></Link>)}
        </Menu>
      ) )}
    </>
  );
}

export default SetURL;