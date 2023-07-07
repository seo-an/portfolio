import { useEffect, useState, useCallback } from "react";

// import { Container, Wrapper, ButtonContainer, FlipButton as Button, Title, GridTable, TableCell, TableCellText, YearWrapper as Year, MonthWrapper as Month } from "../../view/pages/CalendarView";
import { CalendarView } from "../../view/pages/CalendarView";


export const Calendar = () => {
  const [now, setNow] = useState(getDates());
  const [temp, setTemp] = useState(getDates());
  const [calendar, setCalendar] = useState([]);

  const buttonText = {
    prev: '<',
    next: '>',
    today: '오늘'
  }


  // Basic Settings
  function setDateInfo(dat) {
    const year = dat.getFullYear();
    const month = dat.getMonth();
    const date = dat.getDate();
    const day = dat.getDay();

    const thisOne = {
      year: year,
      month: month,
      date: date,
      day: day,
    }
  
    const r = Object.values(thisOne);
    return r;
  }


  function getDates(d) {
    const dat = (d === undefined ? new Date() : new Date(d));
    const r = setDateInfo(dat);

    return r;
  }


  function getDateString(arry) {
    const data = [...arry];

    const yy = data[0];
    const mm = data[1] + 1;
    const dd = data[2];

    const string = `${yy}-${(mm < 10 ? '0'+mm : mm)}-${dd}`;
    return string;
  }


  // 달의 마지막 날짜
  const getEndOfMonth = (arry) => {
    const date = [...arry];

    const yy = date[0];
    const mm = date[1];

    const leap = (new Date(yy, 2, 0).getDate() === 29 ? 29 : 28);
  
    const lastDatesOfMonth = [31, leap, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    const lastDateOfThisMonth = lastDatesOfMonth[mm];
    return lastDateOfThisMonth;
  }


  // 달의 첫 시작 요일
  const getFirstDayOfMonth = useCallback((arry) => {
    const date = [...arry];

    const yy = date[0];
    const mm = date[1];
    const dd = '01';

    const newDate = [yy, mm, dd];
    const str = getDateString(newDate);

    const firstDay = new Date(str).getDay();
    return firstDay;
  }, [])


  // 달의 마지막 요일
  const getLastDayOfMonth = useCallback((arry) => {
    const date = [...arry];

    const yy = date[0];
    const mm = date[1];
    const dd = getEndOfMonth(date);

    const newDate = [yy, mm, dd];
    const str = getDateString(newDate);

    const lastDay = new Date(str).getDay();
    return lastDay;
  }, [])


  // Interaction function
  const goToLastMonth = () => {
    const data = [...temp];
    if (data[1] === 0) {
      data[1] = 11;
      data[0] = data[0] - 1;
      setTemp(() => data);
    } else {
      data[1] = data[1] - 1;
      setTemp(() => data);
    }
  }


  const goToNextMonth = () => {
    const data = [...temp];
    if (data[1] === 11) {
      data[1] = 0;
      data[0] = data[0] + 1;
      setTemp(() => data);
    } else {
      data[1] = data[1] + 1;
      setTemp(() => data);
    }
  }


  const setDays = useCallback((arry) => {
    const currentDate = [...arry];

    const startDay = getFirstDayOfMonth(currentDate);
    const lastDay = getLastDayOfMonth(currentDate);
    const endDate = getEndOfMonth(currentDate);
    const point = getDateString(now);

    let i = 0;
    let min = (startDay - 1) * -1;

    const weekdays = 7;
    const last = weekdays - lastDay;
    const days = [];
    const spaces = endDate + last;

    // new Date(2022, 10, 0)
    // new Date(2022, 10, -1)
    // new Date(2022, 10, -2)
    while (min < spaces) {
      let day = new Date(currentDate[0], currentDate[1], min);
      let key = (new Date().getMilliseconds()) + min;

      let dayday = [currentDate[0], currentDate[1], min];
      let isToday = getDateString(dayday);

      days[i] = {id: key, year: day.getFullYear(), month: day.getMonth(), date: day.getDate(), day: day.getDay(), onToday: (point === isToday ? true : false)};
      min++;
      i++;
    }

    return days;
  }, [now, getFirstDayOfMonth, getLastDayOfMonth])


  const flipOver = (e) => {
    const val = e.target.innerText;
    if (val === buttonText.today) {
      setNow(() => getDates());
      setTemp(() => now);
      return;
    }
    if (val === buttonText.prev) {
      goToLastMonth();
      // 이 때는 temp가 안변해용
      return;
    }
    if (val === buttonText.next) {
      goToNextMonth();
      // 이 때는 temp가 안변해용
      return;
    }
  }
  

  useEffect(() => {
    // 이 안에서 temp가 최신 값으로 변해용
    // console.info('temp :: ', temp);
    // console.info('now :: ', now);

    setCalendar(() => setDays(temp));

  }, [temp, setDays]);

  const year = temp[0];
  const month = (temp[1] + 1);
  const week = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];


  const calendarProps = {
    year,
    month,
    week,
    calendar,
    buttonText,
    flipOver,
  };

  
  return (
    <CalendarView {...calendarProps}/>
  )
}