import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import styled from "styled-components";

import { FlightApiView } from "../../view/pages/FlightApiView";





// // 공공 API 실습중
// // https://okky.kr/articles/766435


const callAirport = () => {

  const fetchApi = async () => {
    const SERVICE_KEY = process.env.REACT_APP_INCHEON_INT_AIRPORT_WEATHER_INFO_API_KEY;
    const ARRIVAL_URL = `/B551177/StatusOfPassengerWorldWeatherInfo/getPassengerArrivalsWorldWeather`;
    const DEPARTURE_URL = `/B551177/StatusOfPassengerWorldWeatherInfo/getPassengerDeparturesWorldWeather`;
  
    // proxy 통하니까 decoding service key 넣어야 작동했음
    const getApi = await axios({
      method: "GET",
      url: `/weather-api${ARRIVAL_URL}`,
      params: {
        'serviceKey': `${SERVICE_KEY}`,
        'numOfRows': '10', 
        'pageNo': '1', 
        'from_time': '0000', 
        'to_time': '2400', 
        'airport': '',
        'flight_id': '',
        'airline': '',
        'lang':'K', 
        'type':'json'
      },
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 60000,
    })
    .then(response => response.data.response.body)
    .then(data => console.log(data))
    .catch((error) => {
      console.log('! ERROR FAIL TO CONNECT TO fetchApi :: ', error);
    });
  };

  fetchApi();
}


const changeTo = (val) => {
  if (val === '') return;
  else if (typeof(val) === 'string') {
    let result = val.charCodeAt(0);
    return result;
  }
  else if (typeof(val) === 'number') {
    let result = String.fromCharCode(val);
    return result;
  }
};

const handleSearch = (on) => {
  console.log(on);
  if (on) {
    return (
      <div>
          <select>
            <option>1</option>
          </select>
      </div>
    )
  }
};


const letsBreak = (val) => {
  const wordCode = {
    separate: ['가', '까', '나', '다', '따', '라', '마', '바', '빠', '사', '싸', '아', '자', '짜', '차', '카', '타', '파', '하'],
    initial: ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'],
    vowel: ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"],
    last: ['', "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㅀ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
  };

  // 자음(19개) 하나 당 가능한 변화 자음(1개)*모음(21개)*받침(28개) = 588개
  // 28개 단위로 받침이 바뀜
  // 21개 단위로 모음이 바뀜
  // 한 자음에서 모음(21)*받침(28)개를 순환하면 자음이 바뀜
  const theFrstCode = '가'.charCodeAt(0);
  let value = (val === undefined || isNaN(val)) ? null : val;
  if (value === null) return;
  let initialNum = Math.trunc((value - theFrstCode)/588); // 자음 찾기
  let firstWordCode = changeTo(wordCode.separate[initialNum]); // 해당 자음으로 시작하는 가장 첫 단어의 유니코드 찾기 (변화의 단위: 588개, 588개 단위로 자음이 바뀜)
  let vowelNum = Math.trunc((value - firstWordCode) / wordCode.last.length); // 자음1, 모음1의 가능한 변화 = 받침의 개수 (변화의 단위: 28개, 28개 단위로 모음이 바뀜)
  let lastNum = (value - firstWordCode) - (28 * vowelNum); // 가능한 받침 단위(28개) 개수만큼 빼고 남은 나머지 = 받침 순서 (변화의 단위: 1개)
  
  // console.log(theFrstCode, value, firstWordCode, initialNum, vowelNum, lastNum);
  // console.log(wordCode.initial[initialNum], wordCode.vowel[vowelNum], wordCode.last[lastNum]);
  // const breaks = `'${wordCode.initial[initialNum]}', '${wordCode.vowel[vowelNum]}', '${wordCode.last[lastNum]}'`;
  // console.log(breaks);
  const result = `'${wordCode.initial[initialNum]}', '${changeTo(firstWordCode+(28*vowelNum))}', '${changeTo(firstWordCode+(28*vowelNum)+lastNum)}'`;

  return result;
};



export const FlightApiJs = () => {
  // 임시로 안불러옴
  callAirport();
  
  
  const [word, setWord] = useState();
  const [breakWord, setBreakWord] = useState();

  const catchTyping = (e) => {
    const val = e.target.value;
    console.log(val);
    handleSearch(true);
    setWord(val);
  };


  useEffect(() => {
    setBreakWord(letsBreak(changeTo(word)));
  }, [word])
  

  
  console.log(breakWord);


  

  const onSubmit = (e) => {
    e.preventDefault();
    const airlines = document.querySelector("input#airlines").value;
    
  };
  
  const toFlightApiViewProps = {
    onSubmit,
    catchTyping,
    handleSearch,
  }
  
  // console.log(hangulCode.indexOf(air1));

  return (
    <>
      <FlightApiView props={ { ...toFlightApiViewProps } }/>
      {/* <div>
        <form onSubmit={onSubmit}>
          <input name="test" id="airlines" placeholder="항공사" onChange={catchTyping}></input>
        </form>
      </div> */}
    </>
  )
}