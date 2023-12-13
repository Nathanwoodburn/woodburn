const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ/.?!@#$%^&*()_+";

let interval = null;
let interval2 = null;
let interval3 = null;


// window.onload = (event) => {

// target = document.querySelector(".nathanwoodburn");
//   let iteration = 0;
//   let final = "NATHAN.WOODBURN/";
//   clearInterval(interval);
  
//   interval = setInterval(() => {
//     target.innerText = target.innerText
//       .split("")
//       .map((letter, index) => {
//         if(index < iteration) {
//           return final[index];
//         }
      
//         return letters[Math.floor(Math.random() * 41)]
//       })
//       .join("");
    
//     if(iteration >= final.length){ 
//       clearInterval(interval);
//     }
    
//     iteration += 1 / 3;
//   }, 30);
// };

document.querySelector(".copyright").onmouseover = event => {  
    let iteration2 = 0;
    let old2 = "Copyright © Nathan Woodburn 2023";
    console.log(old2);
    clearInterval(interval2);
    
    interval2 = setInterval(() => {
      event.target.innerText = event.target.innerText
        .split("")
        .map((letter, index2) => {
          if(index2 < iteration2) {
            return old2[index2];
          }
        
          return letters[Math.floor(Math.random() * 41)]
        })
        .join("");
      
      if(iteration2 >= old2.length){ 
        clearInterval(interval2);
      }
      
      iteration2 += 1/3;
    }, 10);
  }
  // document.querySelector(".hacker3").onmouseover = event => {  
  //   let iteration3 = 0;
  //   let old3 = event.target.innerText;
  //   console.log(old3);
  //   clearInterval(interval3);
    
  //   interval3 = setInterval(() => {
  //     event.target.innerText = event.target.innerText
  //       .split("")
  //       .map((letter, index3) => {
  //         if(index3 < iteration3) {
  //           return old3[index3];
  //         }
        
  //         return letters[Math.floor(Math.random() * 41)]
  //       })
  //       .join("");
      
  //     if(iteration3 >= old3.length){ 
  //       clearInterval(interval3);
  //     }
      
  //     iteration3 += 1 / 3;
  //   }, 10);
  // }