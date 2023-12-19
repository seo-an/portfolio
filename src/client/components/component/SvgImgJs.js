import { useCallback, useRef, useState } from 'react';
import { SvgImgView } from '../../view/pages/SvgImgView.js';


export const SetColorData = (arry) => {
  const array = [...arry];
  const colorOpt = array.map((item) => (
    {[item.layer]: {
      color: item.color,
      option: item.option}
    }
  ));

  const setting = (fullArry, arry) => {
    let status = {status: true};
    let i = 0;
    while (i < fullArry.length) {
      Object.assign(status, arry[i]);
      i++;
    }
    return status;
  }
  
  const result = setting(array, colorOpt);

  return result;
}


export const SvgImg = () => {
  const childComponentRef = useRef();
  // 자식 component에서 DOM 선택해 event 추가
  // useEffect(() => {
  //   // childComponentRef.current.onclick = ttt;
    
  //   const haha = childComponentRef.current;
  //   haha.addEventListener('click', test);

  // }, []);
  


  // 자식 component에서 prop 받아서 작업
  const [palette, setPalette] = useState([]);

  const getChildData = useCallback((arry) => {
    setPalette(arry);
  }, [setPalette]);
  

  return (
    <SvgImgView getData={getChildData} setData={SetColorData} data={palette} ref={childComponentRef} />
  )
};