%Function used to make response button symbol textures that can be plotted
%by Psychtoolbox.
%Author: Arthur S. Courtin
%License: MIT

function [LbTexture,RbTexture,LsTexture,RsTexture]=make_response_type_images(expWin,response_type,background_color,text_color,middle_color)

    switch response_type
        case 'mouse'
            load('LC.mat');
        case 'keyboard'
            load('LK.mat');
        case 'button box'
            load('LB.mat');
    end

    R=flip(L,2);

    for i=1:3
        Lb(:,:,i)=double(L(:,:))*(background_color(i)-text_color(i))+text_color(i);
        Rb(:,:,i)=double(R(:,:))*(background_color(i)-text_color(i))+text_color(i);
        Ls(:,:,i)=double(L(:,:))*(background_color(i)-middle_color(i))+middle_color(i);
        Rs(:,:,i)=double(R(:,:))*(background_color(i)-middle_color(i))+middle_color(i);
    end
    LbTexture = Screen('MakeTexture', expWin, Lb);
    RbTexture = Screen('MakeTexture', expWin, Rb);
    LsTexture = Screen('MakeTexture', expWin, Ls);
    RsTexture = Screen('MakeTexture', expWin, Rs);
end