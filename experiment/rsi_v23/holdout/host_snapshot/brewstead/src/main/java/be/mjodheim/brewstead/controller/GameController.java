package be.mjodheim.brewstead.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class GameController {

    @GetMapping("/")
    public String home(){
        return "game/brewstead-world";
    }
}
