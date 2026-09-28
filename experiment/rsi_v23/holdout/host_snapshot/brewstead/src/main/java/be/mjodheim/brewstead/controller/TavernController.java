package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.tavern.TavernResponse;
import be.mjodheim.brewstead.service.TavernService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/tavern")
@RequiredArgsConstructor
public class TavernController {

    private final TavernService tavernService;

    @GetMapping
    public TavernResponse tavern() {
        return tavernService.getTavern();
    }
}
